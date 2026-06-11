#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CHOQUE MENTAL 3.0
Sistema cloud: GitHub Actions + Supabase + OpenAlex + Cloudflare Workers AI + Pollinations + FFmpeg + Instagram Graph API.

Modo seguro:
- DRY_RUN=true: gera conteúdo/vídeo e atualiza banco sem publicar no Instagram.
- DRY_RUN=false: publica no Instagram Reels usando URL pública do vídeo no Supabase Storage.

Sem link de afiliado em comentários. CTA aponta para a bio.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
import feedparser
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")


# =========================
# CONFIG
# =========================
@dataclass
class Config:
    supabase_url: str
    supabase_key: str
    supabase_bucket: str
    cf_account_id: str
    cf_api_token: str
    cf_model: str
    ig_user_id: str
    ig_token: str
    openalex_mailto: str
    google_sheets_csv_url: str = ""
    prefer_rss: bool = True
    rss_max_items_per_run: int = 40
    max_posts_per_day: int = 36
    dry_run: bool = True

    @staticmethod
    def from_env() -> "Config":
        def env(name: str, default: str = "") -> str:
            return os.getenv(name, default).strip()

        required = [
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
            "SUPABASE_BUCKET",
            "CLOUDFLARE_ACCOUNT_ID",
            "CLOUDFLARE_API_TOKEN",
        ]
        missing = [x for x in required if not env(x)]
        if missing:
            raise RuntimeError(f"Variáveis ausentes: {', '.join(missing)}")

        dry = env("DRY_RUN", "true").lower() in {"1", "true", "yes", "sim"}
        return Config(
            supabase_url=env("SUPABASE_URL").rstrip("/"),
            supabase_key=env("SUPABASE_SERVICE_ROLE_KEY"),
            supabase_bucket=env("SUPABASE_BUCKET", "choque-videos"),
            cf_account_id=env("CLOUDFLARE_ACCOUNT_ID"),
            cf_api_token=env("CLOUDFLARE_API_TOKEN"),
            cf_model=env("CLOUDFLARE_MODEL", "@cf/meta/llama-3.1-8b-instruct"),
            ig_user_id=env("IG_USER_ID"),
            ig_token=env("INSTAGRAM_ACCESS_TOKEN"),
            openalex_mailto=env("OPENALEX_MAILTO", "bot@example.com"),
            google_sheets_csv_url=env("GOOGLE_SHEETS_CSV_URL", ""),
            prefer_rss=env("PREFER_RSS", "true").lower() in {"1", "true", "yes", "sim"},
            rss_max_items_per_run=int(env("RSS_MAX_ITEMS_PER_RUN", "40") or "40"),
            max_posts_per_day=int(env("MAX_POSTS_PER_DAY", "36") or "36"),
            dry_run=dry,
        )


CFG = Config.from_env()


# =========================
# HTTP BASE
# =========================
def supabase_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {
        "apikey": CFG.supabase_key,
        "Authorization": f"Bearer {CFG.supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if extra:
        h.update(extra)
    return h


def rest_url(path: str) -> str:
    return f"{CFG.supabase_url}/rest/v1/{path.lstrip('/')}"


def storage_url(path: str) -> str:
    return f"{CFG.supabase_url}/storage/v1/{path.lstrip('/')}"


def request_json(method: str, url: str, **kwargs) -> Any:
    r = requests.request(method, url, timeout=90, **kwargs)
    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code} em {url}: {r.text[:1000]}")
    if not r.text:
        return None
    return r.json()


# =========================
# LOGS
# =========================
def log_exec(etapa: str, status: str, detalhe: str = "", post_id: Optional[int] = None) -> None:
    payload = {"etapa": etapa, "status": status, "detalhe": detalhe[:2000]}
    if post_id:
        payload["post_id"] = post_id
    try:
        requests.post(rest_url("execucoes"), headers=supabase_headers(), json=payload, timeout=30)
    except Exception as e:
        print(f"[WARN] Falha ao registrar log: {e}", file=sys.stderr)


# =========================
# SUPABASE POSTS
# =========================
def selecionar_post() -> Optional[Dict[str, Any]]:
    # Bloqueio simples: pega o primeiro agendado e marca processando.
    # Para múltiplos runners simultâneos, prefira RPC com SELECT FOR UPDATE.
    url = rest_url("posts?status=eq.agendado&order=indice_uso.asc,engajamento_score.desc,id.asc&limit=1")
    data = request_json("GET", url, headers=supabase_headers())
    if not data:
        return None
    post = data[0]
    atualizar_post(post["id"], {"status": "processando", "erro": None})
    post["status"] = "processando"
    return post


def atualizar_post(post_id: int, fields: Dict[str, Any]) -> Dict[str, Any]:
    url = rest_url(f"posts?id=eq.{post_id}")
    data = request_json("PATCH", url, headers=supabase_headers(), json=fields)
    return data[0] if data else {}


def limite_diario_atingido() -> bool:
    if CFG.max_posts_per_day <= 0:
        return False
    hoje = datetime.now(timezone.utc).date().isoformat()
    url = rest_url(f"posts?status=eq.postado&data_publicacao=gte.{hoje}T00:00:00Z&select=id")
    try:
        data = request_json("GET", url, headers=supabase_headers())
        total = len(data or [])
        if total >= CFG.max_posts_per_day:
            log_exec("limite_diario", "ok", f"Limite atingido: {total}/{CFG.max_posts_per_day}")
            return True
    except Exception as e:
        log_exec("limite_diario", "warn", str(e))
    return False


def inserir_metrica(post_id: int, media_id: Optional[str], metrics: Dict[str, int]) -> None:
    score = calcular_score(metrics)
    payload = {
        "post_id": post_id,
        "instagram_media_id": media_id,
        "curtidas": metrics.get("curtidas", 0),
        "comentarios": metrics.get("comentarios", 0),
        "compartilhamentos": metrics.get("compartilhamentos", 0),
        "salvamentos": metrics.get("salvamentos", 0),
        "alcance": metrics.get("alcance", 0),
        "impressoes": metrics.get("impressoes", 0),
        "score": score,
    }
    request_json("POST", rest_url("metricas"), headers=supabase_headers(), json=payload)
    atualizar_post(post_id, {"engajamento_score": score})


# =========================
# RSS + GOOGLE SHEETS AUXILIAR
# =========================
def classificar_pilar(texto: str, fallback: str = "Cérebro e Percepção") -> str:
    t = texto.lower()
    regras = [
        ("Sono e Energia", ["sleep", "circadian", "melatonin", "insomnia", "caffeine", "cortisol", "mitochondria", "sono", "melatonina"]),
        ("Psicologia Sombria", ["bias", "manipulation", "persuasion", "deception", "social influence", "obedience", "dark triad", "maquiavel", "manipula"]),
        ("Relacionamentos", ["relationship", "attachment", "dating", "attraction", "romantic", "partner", "oxytocin", "relacionamento", "apego"]),
        ("Dinheiro e Consumo", ["consumer", "money", "spending", "price", "marketing", "economics", "choice architecture", "consumo", "dinheiro"]),
        ("Produtividade", ["productivity", "focus", "attention", "deep work", "habit", "flow", "procrastination", "produtividade", "foco"]),
        ("Fatos Absurdos", ["experiment", "strange", "weird", "bizarre", "history", "milgram", "stanford", "absurd", "bizarro"]),
        ("Cérebro e Percepção", ["brain", "neuroscience", "memory", "perception", "neuroplasticity", "illusion", "cognition", "cérebro", "memória"]),
    ]
    for pilar, keys in regras:
        if any(k in t for k in keys):
            return pilar
    return fallback


def carregar_rss_sources() -> list[dict]:
    try:
        data = request_json(
            "GET",
            rest_url("rss_sources?ativo=eq.true&select=*&order=prioridade.asc,id.asc"),
            headers=supabase_headers(),
        )
        return data or []
    except Exception as e:
        log_exec("rss_sources", "warn", f"Usando lista interna. Motivo: {e}")
        return []


def entry_datetime_iso(entry: Any) -> Optional[str]:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc).isoformat()
        except Exception:
            return None
    return None


def json_safe(obj: Any) -> Any:
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {"raw_string": str(obj)[:5000]}


def coletar_rss_items() -> None:
    sources = carregar_rss_sources()
    if not sources:
        return
    total = 0
    for src in sources:
        if total >= CFG.rss_max_items_per_run:
            break
        feed_url = src.get("url")
        if not feed_url:
            continue
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:10]:
                if total >= CFG.rss_max_items_per_run:
                    break
                link = entry.get("link") or entry.get("id") or ""
                title = entry.get("title") or ""
                summary = re.sub(r"<[^>]+>", " ", entry.get("summary", ""))
                if not link or not title:
                    continue
                pilar = src.get("pilar_padrao") or classificar_pilar(f"{title} {summary}")
                payload = {
                    "source_id": src.get("id"),
                    "source_name": src.get("nome"),
                    "pilar": pilar,
                    "titulo": title[:500],
                    "resumo": summary[:6000],
                    "link": link[:1000],
                    "published_at": entry_datetime_iso(entry),
                    "raw": json_safe(entry),
                }
                r = requests.post(rest_url("rss_items"), headers=supabase_headers({"Prefer": "resolution=ignore-duplicates"}), json=payload, timeout=30)
                if r.status_code in {200, 201}:
                    total += 1
        except Exception as e:
            log_exec("rss_coleta", "warn", f"{src.get('nome')}: {e}")
    if total:
        log_exec("rss_coleta", "ok", f"Itens processados: {total}")


def buscar_rss_item_para_post(post: Dict[str, Any]) -> Optional[Dict[str, str]]:
    # Tenta notícia viva do mesmo pilar. Se não houver, OpenAlex assume.
    try:
        url = rest_url(
            "rss_items?usado=eq.false"
            f"&pilar=eq.{urllib.parse.quote(post['pilar'])}"
            "&order=published_at.desc.nullslast,created_at.desc&limit=1"
        )
        data = request_json("GET", url, headers=supabase_headers())
        if not data:
            return None
        item = data[0]
        request_json("PATCH", rest_url(f"rss_items?id=eq.{item['id']}"), headers=supabase_headers(), json={"usado": True, "post_id": post["id"]})
        return {
            "titulo": item.get("titulo") or post["subtema"],
            "resumo": item.get("resumo") or f"Notícia científica de {item.get('source_name', 'RSS')}",
            "link": item.get("link") or "",
            "fonte_tipo": "RSS",
            "fonte_nome": item.get("source_name") or "RSS",
        }
    except Exception as e:
        log_exec("rss_selecao", "warn", str(e), int(post["id"]))
        return None


def importar_google_sheets_posts() -> None:
    # Free: publique a aba como CSV e use GOOGLE_SHEETS_CSV_URL.
    if not CFG.google_sheets_csv_url:
        return
    import csv
    import io
    try:
        r = requests.get(CFG.google_sheets_csv_url, timeout=60)
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        rows = csv.DictReader(io.StringIO(r.text))
        count = 0
        for row in rows:
            tema = (row.get("tema_base") or "").strip()
            pilar = (row.get("pilar") or "").strip()
            subtema = (row.get("subtema") or "").strip()
            status = (row.get("status") or "agendado").strip() or "agendado"
            if not tema or not pilar or not subtema:
                continue
            payload = {"tema_base": tema, "pilar": pilar, "subtema": subtema, "status": status}
            # Sem constraint única obrigatória em posts; a tabela sheets_import_log evita duplicação lógica.
            key = slugify(f"{tema}-{pilar}-{subtema}")
            exists = request_json("GET", rest_url(f"sheets_import_log?chave=eq.{urllib.parse.quote(key)}&limit=1"), headers=supabase_headers())
            if exists:
                continue
            created = request_json("POST", rest_url("posts"), headers=supabase_headers(), json=payload)
            pid = created[0]["id"] if created else None
            request_json("POST", rest_url("sheets_import_log"), headers=supabase_headers(), json={"chave": key, "post_id": pid, "raw": row})
            count += 1
        if count:
            log_exec("google_sheets", "ok", f"Posts importados: {count}")
    except Exception as e:
        log_exec("google_sheets", "warn", str(e))


def calcular_score(m: Dict[str, int]) -> float:
    # Salvamento e compartilhamento pesam mais porque indicam valor/viralidade.
    return round(
        m.get("curtidas", 0) * 1.0
        + m.get("comentarios", 0) * 2.5
        + m.get("compartilhamentos", 0) * 5.0
        + m.get("salvamentos", 0) * 4.0
        + m.get("alcance", 0) * 0.02,
        4,
    )


# =========================
# OPENALEX
# =========================
def reconstruir_abstract(inv: Optional[Dict[str, Any]]) -> str:
    if not inv:
        return ""
    words = []
    positions = []
    for word, poss in inv.items():
        for p in poss:
            positions.append((p, word))
    for _, word in sorted(positions):
        words.append(word)
    return " ".join(words)


def buscar_artigo(post: Dict[str, Any]) -> Dict[str, str]:
    if CFG.prefer_rss:
        rss_item = buscar_rss_item_para_post(post)
        if rss_item:
            atualizar_post(post["id"], {
                "titulo_artigo": rss_item["titulo"],
                "resumo_artigo": rss_item["resumo"][:6000],
                "link_artigo": rss_item["link"],
            })
            return rss_item

    if post.get("link_artigo") and post.get("resumo_artigo"):
        return {
            "titulo": post.get("titulo_artigo") or post["subtema"],
            "resumo": post.get("resumo_artigo") or "",
            "link": post.get("link_artigo") or "",
        }

    query = f"{post['subtema']} {post['tema_base']} {post['pilar']} psychology neuroscience behavior"
    params = {
        "search": query,
        "per-page": 5,
        "mailto": CFG.openalex_mailto,
        "filter": "is_paratext:false",
    }
    url = "https://api.openalex.org/works"
    r = requests.get(url, params=params, timeout=60)
    if not r.ok:
        raise RuntimeError(f"OpenAlex erro {r.status_code}: {r.text[:500]}")
    results = r.json().get("results", [])
    if not results:
        return {
            "titulo": post["subtema"],
            "resumo": f"Tema editorial: {post['subtema']} dentro de {post['pilar']}. Use linguagem cautelosa e não invente dados.",
            "link": "https://openalex.org/",
        }

    # Prioriza artigo com abstract.
    chosen = None
    for item in results:
        if item.get("abstract_inverted_index"):
            chosen = item
            break
    chosen = chosen or results[0]

    titulo = chosen.get("display_name") or post["subtema"]
    resumo = reconstruir_abstract(chosen.get("abstract_inverted_index"))
    if not resumo:
        resumo = chosen.get("title") or titulo
    link = chosen.get("doi") or chosen.get("id") or "https://openalex.org/"

    atualizar_post(post["id"], {
        "titulo_artigo": titulo,
        "resumo_artigo": resumo[:6000],
        "link_artigo": link,
    })

    return {"titulo": titulo, "resumo": resumo[:6000], "link": link}


# =========================
# PROMPT + CLOUDFLARE AI
# =========================
def carregar_prompt_master() -> str:
    return (ROOT / "prompt_master.md").read_text(encoding="utf-8")


def modo_reciclagem(post: Dict[str, Any]) -> str:
    if (post.get("engajamento_score") or 0) >= 50:
        return "alto_engajamento"
    if (post.get("indice_uso") or 0) > 0:
        return "reciclagem"
    return "novo"


def gerar_conteudo(post: Dict[str, Any], artigo: Dict[str, str]) -> Dict[str, str]:
    system = carregar_prompt_master()
    user = f"""
Pilar: {post['pilar']}
Tema base: {post['tema_base']}
Subtema: {post['subtema']}
Título do artigo: {artigo['titulo']}
Resumo científico: {artigo['resumo'][:5000]}
Link do artigo: {artigo['link']}
Modo de reciclagem: {modo_reciclagem(post)}

Gere a saída exatamente no formato obrigatório.
""".strip()
  ponto_final = f"https://api.cloudflare.com/client/v4/accounts/{CFG.cf_account_id}/ai/run/{CFG.cf_model}"

    print("CF_ACCOUNT_ID =", CFG.cf_account_id)
    print("CF_MODEL =", CFG.cf_model)
    print("ENDPOINT =", ponto_final)

    headers = {
        "Authorization": f"Bearer {CFG.cf_api_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messages": [
            {"role": "system", "content": sistema},
            {"role": "user", "content": usuario},
        ],
        "temperature": 0.75,
        "max_tokens": 1200,
    }

    r = requests.post(
        ponto_final,
        headers=headers,
        json=payload,
        timeout=120
    )

    if not r.ok:
        raise RuntimeError(
            f"Cloudflare AI erro {r.status_code}: {r.text[:1000]}"
        )

    data = r.json()

    text = (
        data.get("result", {}).get("response")
        or data.get("result", {}).get("text")
        or ""
    )

    if not text:
        raise RuntimeError(
            f"Resposta vazia Cloudflare: {json.dumps(data)[:1000]}"
        )

    parsed = parse_blocos(text)

    validar_conteudo(parsed)

    return parsed

def parse_blocos(text: str) -> Dict[str, str]:
    labels = ["HOOK", "MIDIA_TEXTO", "LEGENDA", "IMAGE_PROMPT", "CTA_BIO"]
    out: Dict[str, str] = {}
    for i, label in enumerate(labels):
        start = f"[{label}]"
        end = f"[{labels[i + 1]}]" if i + 1 < len(labels) else None
        if start not in text:
            out[label.lower()] = ""
            continue
        chunk = text.split(start, 1)[1]
        if end and end in chunk:
            chunk = chunk.split(end, 1)[0]
        out[label.lower()] = chunk.strip()
    return out

def validar_conteudo(c: Dict[str, str]) -> None:
    required = ["hook", "midia_texto", "legenda", "image_prompt", "cta_bio"]
    missing = [k for k in required if not c.get(k)]
    if missing:
        raise RuntimeError(f"Blocos ausentes: {missing}. Conteúdo: {c}")
    c["hook"] = c["hook"][:110]
    c["midia_texto"] = c["midia_texto"][:260]
    c["legenda"] = c["legenda"][:2200]


# =========================
# MÍDIA
# =========================
def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:80] or "choque"


def baixar_imagem(prompt: str, dest: Path) -> None:
    # Pollinations endpoint público. Sem texto na imagem; texto entra no FFmpeg.
    prompt_full = f"{prompt}, vertical 9:16, no text, no watermark"
    encoded = urllib.parse.quote(prompt_full)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&enhance=true"
    r = requests.get(url, timeout=180)
    if not r.ok or not r.content:
        raise RuntimeError(f"Pollinations erro {r.status_code}: {r.text[:200]}")
    dest.write_bytes(r.content)


def escrever_textfile(text: str, path: Path) -> None:
    text = text.replace("\r", " ").replace("\n", "\\n")
    path.write_text(text, encoding="utf-8")


def localizar_fonte() -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return "DejaVuSans-Bold"


def montar_video(image_path: Path, hook: str, midia_texto: str, output_path: Path) -> None:
    hook_file = OUT / "hook.txt"
    body_file = OUT / "body.txt"
    escrever_textfile(hook.upper(), hook_file)
    escrever_textfile(midia_texto, body_file)
    font = localizar_fonte()

    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "eq=contrast=1.25:saturation=0.42:brightness=-0.035,"
        "noise=alls=24:allf=t+u,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.18:t=fill,"
        f"drawtext=fontfile='{font}':textfile='{hook_file}':"
        "fontcolor=yellow:fontsize=70:line_spacing=12:box=1:boxcolor=black@0.62:boxborderw=28:"
        "x=(w-text_w)/2:y=(h-text_h)/2-170,"
        f"drawtext=fontfile='{font}':textfile='{body_file}':"
        "fontcolor=white:fontsize=44:line_spacing=10:box=1:boxcolor=black@0.55:boxborderw=22:"
        "x=(w-text_w)/2:y=(h-text_h)/2+170,"
        "format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", vf,
        "-t", "10",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou:\n{proc.stderr[-3000:]}")


# =========================
# SUPABASE STORAGE
# =========================
def upload_video(path: Path, post_id: int) -> Tuple[str, str]:
    storage_path = f"posts/{post_id}/{int(time.time())}-{path.name}"
    url = storage_url(f"object/{CFG.supabase_bucket}/{storage_path}")
    headers = {
        "apikey": CFG.supabase_key,
        "Authorization": f"Bearer {CFG.supabase_key}",
        "Content-Type": "video/mp4",
        "x-upsert": "true",
    }
    r = requests.post(url, headers=headers, data=path.read_bytes(), timeout=180)
    if not r.ok:
        raise RuntimeError(f"Upload Storage erro {r.status_code}: {r.text[:1000]}")
    public_url = storage_url(f"object/public/{CFG.supabase_bucket}/{storage_path}")
    return storage_path, public_url


# =========================
# INSTAGRAM GRAPH API
# =========================
def publicar_instagram(video_url: str, caption: str) -> str:
    if not CFG.ig_user_id or not CFG.ig_token:
        raise RuntimeError("IG_USER_ID ou INSTAGRAM_ACCESS_TOKEN ausente.")

    base = f"https://graph.facebook.com/v20.0/{CFG.ig_user_id}"
    create_payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": CFG.ig_token,
    }
    container = request_json("POST", f"{base}/media", data=create_payload)
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(f"Container sem id: {container}")

    # Aguarda processamento do container.
    status_url = f"https://graph.facebook.com/v20.0/{creation_id}"
    for _ in range(30):
        s = request_json("GET", status_url, params={
            "fields": "status_code,status",
            "access_token": CFG.ig_token,
        })
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code == "ERROR":
            raise RuntimeError(f"Instagram container erro: {s}")
        time.sleep(10)

    published = request_json("POST", f"{base}/media_publish", data={
        "creation_id": creation_id,
        "access_token": CFG.ig_token,
    })
    media_id = published.get("id")
    if not media_id:
        raise RuntimeError(f"Publicação sem media id: {published}")
    return media_id


def coletar_metricas_instagram(media_id: str) -> Dict[str, int]:
    # Nem todas as contas/mídias retornam todos os insights.
    # Para Reels, nomes podem variar conforme permissão/API.
    metrics = {
        "curtidas": 0,
        "comentarios": 0,
        "compartilhamentos": 0,
        "salvamentos": 0,
        "alcance": 0,
        "impressoes": 0,
    }
    if not media_id or not CFG.ig_token:
        return metrics

    try:
        info = request_json("GET", f"https://graph.facebook.com/v20.0/{media_id}", params={
            "fields": "like_count,comments_count",
            "access_token": CFG.ig_token,
        })
        metrics["curtidas"] = int(info.get("like_count") or 0)
        metrics["comentarios"] = int(info.get("comments_count") or 0)
    except Exception as e:
        print(f"[WARN] Métricas básicas indisponíveis: {e}")

    try:
        insight = request_json("GET", f"https://graph.facebook.com/v20.0/{media_id}/insights", params={
            "metric": "reach,saved,shares,plays",
            "access_token": CFG.ig_token,
        })
        for row in insight.get("data", []):
            name = row.get("name")
            value = int((row.get("values") or [{}])[0].get("value") or 0)
            if name == "reach":
                metrics["alcance"] = value
            elif name == "saved":
                metrics["salvamentos"] = value
            elif name == "shares":
                metrics["compartilhamentos"] = value
            elif name == "plays":
                metrics["impressoes"] = value
    except Exception as e:
        print(f"[WARN] Insights indisponíveis: {e}")

    return metrics


# =========================
# RECICLAGEM + MÉTRICAS
# =========================
def reciclar_antigos() -> None:
    # Usa função SQL criada no schema. Ignora se falhar.
    try:
        url = f"{CFG.supabase_url}/rest/v1/rpc/reciclar_posts_antigos"
        result = request_json("POST", url, headers=supabase_headers(), json={})
        log_exec("reciclagem", "ok", f"Posts reciclados: {result}")
    except Exception as e:
        log_exec("reciclagem", "warn", str(e))


def atualizar_metricas_recentes(limit: int = 6) -> None:
    if CFG.dry_run or not CFG.ig_token:
        return
    url = rest_url(
        "posts?status=eq.postado&instagram_media_id=not.is.null"
        "&order=data_publicacao.desc&limit=" + str(limit)
    )
    try:
        posts = request_json("GET", url, headers=supabase_headers())
        for p in posts:
            m = coletar_metricas_instagram(p["instagram_media_id"])
            inserir_metrica(p["id"], p["instagram_media_id"], m)
    except Exception as e:
        log_exec("metricas", "warn", str(e))


# =========================
# MAIN
# =========================
def main() -> None:
    print("=== CHOQUE MENTAL 3.0 iniciado ===")
    reciclar_antigos()
    importar_google_sheets_posts()
    coletar_rss_items()
    atualizar_metricas_recentes()

    if limite_diario_atingido():
        print("Limite diário atingido. Encerrando sem postar.")
        return

    post = selecionar_post()
    if not post:
        print("Nenhum post agendado.")
        return

    post_id = int(post["id"])
    log_exec("selecionar_post", "ok", f"Post {post_id}", post_id)

    try:
        artigo = buscar_artigo(post)
        log_exec("openalex", "ok", artigo.get("titulo", "")[:300], post_id)

        conteudo = gerar_conteudo(post, artigo)
        log_exec("cloudflare_ai", "ok", conteudo["hook"], post_id)

        atualizar_post(post_id, {
            "link_artigo": artigo.get("link"),
            "titulo_artigo": artigo.get("titulo"),
            "resumo_artigo": artigo.get("resumo")[:6000],
            "hook_gerado": conteudo["hook"],
            "midia_texto": conteudo["midia_texto"],
            "legenda": conteudo["legenda"],
            "image_prompt": conteudo["image_prompt"],
            "cta_bio": conteudo["cta_bio"],
        })

        slug = slugify(f"{post_id}-{conteudo['hook']}")
        image_path = OUT / f"{slug}.jpg"
        video_path = OUT / f"{slug}.mp4"

        baixar_imagem(conteudo["image_prompt"], image_path)
        log_exec("pollinations", "ok", str(image_path.name), post_id)

        montar_video(image_path, conteudo["hook"], conteudo["midia_texto"], video_path)
        log_exec("ffmpeg", "ok", str(video_path.name), post_id)

        storage_path, public_url = upload_video(video_path, post_id)
        log_exec("storage", "ok", public_url, post_id)

        media_id = None
        if CFG.dry_run:
            media_id = f"DRY_RUN_{post_id}_{int(time.time())}"
            print(f"[DRY_RUN] Vídeo pronto: {video_path}")
            print(f"[DRY_RUN] URL pública: {public_url}")
            print(f"[DRY_RUN] Legenda:\n{conteudo['legenda']}")
        else:
            media_id = publicar_instagram(public_url, conteudo["legenda"])
            log_exec("instagram", "ok", media_id, post_id)

        atualizar_post(post_id, {
            "status": "postado",
            "data_publicacao": datetime.now(timezone.utc).isoformat(),
            "instagram_media_id": media_id,
            "video_storage_path": storage_path,
            "video_public_url": public_url,
            "erro": None,
        })

        if not CFG.dry_run and media_id:
            m = coletar_metricas_instagram(media_id)
            inserir_metrica(post_id, media_id, m)

        print("=== CHOQUE MENTAL 3.0 finalizado com sucesso ===")

    except Exception as e:
        err = str(e)
        print(f"[ERRO] {err}", file=sys.stderr)
        atualizar_post(post_id, {"status": "erro", "erro": err[:2000]})
        log_exec("erro", "fail", err, post_id)
        raise


if __name__ == "__main__":
    main()
