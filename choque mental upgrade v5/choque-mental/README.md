# ⚙️ CHOQUE MENTAL — ARQUITETURA DEFINITIVA 3.0

Sistema cloud de produção cognitiva automatizada:

```text
GitHub Actions → Python Bot → Supabase → RSS/OpenAlex/Google Sheets → Cloudflare AI → Pollinations → FFmpeg → Supabase Storage → Instagram API → Métricas
```

Sem servidor fixo. Sem Canva. Sem n8n. Sem link de afiliado nos comentários. Monetização direcionada pela bio.

---

## Arquivos

```text
bot_choque.py                         Script principal
supabase_schema.sql                    Estrutura SQL pronta para colar no Supabase
prompt_master.md                       Prompt mestre por pilar + branding brutalista
engajamento.md                         Sistema de análise de engajamento
plano_10000.md                         Plano matemático para 10.000 seguidores
branding_brutalista.md                 Filosofia, voz, tom e identidade visual
instagram_meta_config.md               Configuração oficial Instagram/Meta
protocolo_anti_shadowban.md            Protocolo de segurança e redução de risco
google_sheets_estrutura.md             Banco auxiliar Google Sheets
midia_gratuita.md                      Geração gratuita de texto, imagem e vídeo
roadmap_90dias_1ano.md                 Roadmap de 90 dias e 1 ano
.github/workflows/choque.yml           GitHub Actions cron a cada 40 min
requirements.txt                       Dependências Python
.env.example                           Modelo de variáveis locais
```

---

## 1. Configurar Supabase

1. Crie um projeto no Supabase.
2. Abra **SQL Editor**.
3. Cole o conteúdo de `supabase_schema.sql`.
4. Execute.
5. Vá em **Storage**.
6. Crie um bucket público chamado:

```text
choque-videos
```

Se preferir outro nome, ajuste `SUPABASE_BUCKET`.

---

## 2. Configurar GitHub Secrets

No repositório:

```text
Settings → Secrets and variables → Actions → New repository secret
```

Crie:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_BUCKET
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_API_TOKEN
CLOUDFLARE_MODEL
IG_USER_ID
INSTAGRAM_ACCESS_TOKEN
OPENALEX_MAILTO
PREFER_RSS
RSS_MAX_ITEMS_PER_RUN
GOOGLE_SHEETS_CSV_URL
MAX_POSTS_PER_DAY
DRY_RUN
```

Sugestão inicial:

```text
DRY_RUN=true
```

Só mude para `false` quando vídeo, storage e legenda estiverem validados.

---

## 3. Cloudflare Workers AI

Use um token com permissão para Workers AI.

Modelo sugerido:

```text
@cf/meta/llama-3.1-8b-instruct
```

Se a conta tiver outro modelo ativo, altere `CLOUDFLARE_MODEL`.

---

## 4. Instagram Graph API

Requisitos gerais:

- Conta Instagram profissional.
- Página do Facebook conectada.
- App Meta configurado.
- Permissões de publicação e leitura de mídia.
- Token de longa duração.

O bot publica Reels usando vídeo hospedado no Supabase Storage público.

---

## 5. Rodar localmente

```bash
cd choque-mental
cp .env.example .env
# edite .env
pip install -r requirements.txt
python bot_choque.py
```

Para testar sem publicar:

```text
DRY_RUN=true
```

---

## 6. Cron de 40 minutos

O workflow usa dois cron jobs porque `*/40` não gera intervalos perfeitamente iguais no GitHub Actions.

Padrão:

```text
00 → 40 → 20 → 00...
```

Para controlar volume e proteger conta/free tier, use:

```text
MAX_POSTS_PER_DAY=36
```

Se quiser começar mais conservador:

```text
MAX_POSTS_PER_DAY=12
```

---

## 7. Fluxo do Bot

1. Recicla posts com mais de 60 dias.
2. Atualiza métricas recentes, se `DRY_RUN=false`.
3. Seleciona próximo post `agendado`.
4. Marca como `processando`.
5. Coleta RSS científico ao vivo e importa Google Sheets, se configurado.
6. Busca notícia RSS do mesmo pilar; se não houver, busca artigo no OpenAlex.
7. Envia fonte científica + pilar para Cloudflare Workers AI.
8. Recebe hook, texto de mídia, legenda, prompt de imagem e CTA para bio.
9. Gera imagem via Pollinations.
10. Monta vídeo vertical com FFmpeg.
11. Faz upload do MP4 no Supabase Storage.
12. Se `DRY_RUN=false`, publica no Instagram.
13. Atualiza Supabase com status, link e métricas.

---

## 8. Monetização pela Bio

O sistema não publica link de afiliado em comentários.

CTA padrão:

```text
A curadoria completa está na bio.
```

Na bio, use um link central com:

- Produto próprio.
- Lista de espera.
- Comunidade.
- E-book.
- Curadoria de livros.
- Newsletter.

---

## 9. Segurança

Nunca coloque chaves dentro do código.

Use apenas:

```text
GitHub Secrets
.env local ignorado pelo git
Supabase Service Role somente no backend/GitHub Actions
```

---

## 10. Ativação

Ordem recomendada:

1. Rodar SQL.
2. Criar bucket público.
3. Subir arquivos no GitHub.
4. Criar secrets com `DRY_RUN=true`.
5. Rodar workflow manual.
6. Conferir `output`, Supabase e Storage.
7. Corrigir se necessário.
8. Mudar `DRY_RUN=false`.
9. Ativar cron.

---

## 11. Banco Científico Infinito via RSS

O schema cria as tabelas:

```text
rss_sources
rss_items
```

Fontes iniciais:

```text
ScienceDaily — Neuroscience
ScienceDaily — Psychology
ScienceDaily — Sleep Disorders
EurekAlert — News Releases
PsyPost — Psychology News
Psychology Today — Latest
```

O bot coleta notícias, classifica por pilar e usa RSS antes do OpenAlex quando:

```text
PREFER_RSS=true
```

Se uma fonte mudar ou falhar, o bot registra aviso em `execucoes` e continua.

---

## 12. Google Sheets Auxiliar

Use quando quiser adicionar pautas manualmente sem abrir o Supabase.

Publique a planilha como CSV e configure:

```text
GOOGLE_SHEETS_CSV_URL
```

Estrutura detalhada em:

```text
google_sheets_estrutura.md
```

---

## 13. Protocolo de Segurança

Não existe garantia real de anti-shadowban. O projeto usa API oficial, variação editorial, CTA pela bio e redução de comportamento repetitivo.

Detalhes em:

```text
protocolo_anti_shadowban.md
```
