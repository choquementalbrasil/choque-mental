# Geração de Mídia Gratuita — Texto + Imagem + Vídeo

## Texto

Motor:

```text
Cloudflare Workers AI
```

Entrada:

- Pilar
- Tema base
- Subtema
- Artigo OpenAlex ou notícia RSS
- Modo: novo, reciclagem ou alto_engajamento

Saída:

```text
HOOK
MIDIA_TEXTO
LEGENDA
IMAGE_PROMPT
CTA_BIO
```

## Imagem

Motor:

```text
Pollinations
```

Custo:

```text
0,00
```

Regras:

- Vertical 9:16
- Sem texto
- Sem watermark
- Brutalista
- Alto contraste
- Preto/branco/amarelo/vermelho
- Sem rosto de influencer

## Vídeo

Motor:

```text
FFmpeg
```

O vídeo é montado com:

- Imagem gerada
- Ruído visual
- Contraste elevado
- Saturação reduzida
- Box preto translúcido
- Hook amarelo central
- Texto branco complementar

## Hospedagem Temporária

Motor:

```text
Supabase Storage público
```

Necessário porque o Instagram Graph API precisa acessar uma URL pública HTTPS.

## Publicação

Motor:

```text
Instagram Graph API
```

Fluxo:

```text
MP4 → Supabase Storage → URL pública → Instagram container → publicação
```

## Custo Operacional

```text
GitHub Actions free tier
Supabase free tier
Cloudflare Workers AI free/limites disponíveis conforme conta
Pollinations público
OpenAlex gratuito
RSS gratuito
FFmpeg open-source
Google Sheets gratuito
```

A arquitetura foi desenhada para operar no gratuito, mas cada plataforma pode alterar limites. O bot registra erro e não trava o sistema inteiro.
