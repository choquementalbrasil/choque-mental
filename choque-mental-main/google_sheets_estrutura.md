# Banco de Dados Auxiliar — Google Sheets

## Função

O Google Sheets serve como painel editorial gratuito para adicionar temas sem mexer no Supabase diretamente.

O bot pode importar a planilha se ela estiver publicada como CSV.

## Configuração Free

1. Crie uma planilha no Google Sheets.
2. Crie uma aba chamada `posts`.
3. Use os cabeçalhos abaixo.
4. Vá em:

```text
Arquivo → Compartilhar → Publicar na Web → CSV
```

5. Copie o link CSV.
6. Coloque no GitHub Secret:

```text
GOOGLE_SHEETS_CSV_URL
```

## Estrutura da Aba posts

| coluna | obrigatório | exemplo |
|---|---|---|
| tema_base | sim | Sono moderno |
| pilar | sim | Sono e Energia |
| subtema | sim | luz azul e ritmo circadiano |
| status | não | agendado |

## Pilares Permitidos

```text
Psicologia Sombria
Sono e Energia
Relacionamentos
Dinheiro e Consumo
Cérebro e Percepção
Fatos Absurdos
Produtividade
```

## Exemplo CSV

```csv
tema_base,pilar,subtema,status
Sono moderno,Sono e Energia,luz azul e ritmo circadiano,agendado
Consumo invisível,Dinheiro e Consumo,preço psicológico,agendado
Manipulação social,Psicologia Sombria,viés de autoridade,agendado
```

## Deduplicação

O bot gera uma chave lógica com:

```text
tema_base + pilar + subtema
```

E registra em:

```text
sheets_import_log
```

Assim, a mesma linha não é importada infinitamente.

## Observação

Este módulo é auxiliar. O cérebro principal continua sendo o Supabase.
