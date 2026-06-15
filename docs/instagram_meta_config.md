# Configuração Oficial do Instagram — Meta for Developers

## Objetivo

Permitir que o bot publique Reels automaticamente usando Instagram Graph API.

## Requisitos

- Conta Instagram profissional: Business ou Creator.
- Página do Facebook conectada ao Instagram.
- App criado no Meta for Developers.
- Permissões corretas aprovadas/configuradas.
- Token de longa duração.
- Vídeo hospedado em URL pública HTTPS.

O projeto usa Supabase Storage público para hospedar o MP4 antes da publicação.

## Variáveis Necessárias

```text
IG_USER_ID
INSTAGRAM_ACCESS_TOKEN
```

## Permissões normalmente necessárias

Dependem da configuração atual da Meta, mas em geral:

```text
instagram_basic
instagram_content_publish
pages_show_list
pages_read_engagement
business_management
```

Para métricas/insights, permissões adicionais podem ser necessárias conforme tipo de conta e app.

## Fluxo de Publicação

```text
1. Bot gera MP4
2. Bot envia para Supabase Storage público
3. Bot cria container de mídia no endpoint /media
4. Bot aguarda status FINISHED
5. Bot publica via /media_publish
6. Bot salva instagram_media_id no Supabase
```

## Segurança

Nunca coloque token no código.
Use apenas:

```text
GitHub Secrets
.env local ignorado pelo git
```

## DRY_RUN

Antes de publicar de verdade:

```text
DRY_RUN=true
```

Depois da validação:

```text
DRY_RUN=false
```

## Observação crítica

A API da Meta muda com frequência. O bot está estruturado para falhar com log claro em `execucoes` caso alguma permissão, endpoint ou token esteja incorreto.
