# Sistema de Análise de Engajamento Inteligente — CHOQUE MENTAL 3.0

## 1. Fórmula de Score

Score base:

```text
score = curtidas*1 + comentarios*2.5 + compartilhamentos*5 + salvamentos*4 + alcance*0.02
```

Interpretação:

- **Curtida**: reação fraca.
- **Comentário**: fricção cognitiva; sinal de debate.
- **Compartilhamento**: viralidade real.
- **Salvamento**: valor percebido e intenção de retorno.
- **Alcance**: distribuição algorítmica.

## 2. Uso do Score

O banco ordena próximos posts por:

```sql
order by indice_uso asc, engajamento_score desc, id asc
```

Isso cria dois efeitos:

1. Não deixa o sistema repetir cedo demais.
2. Dentro do mesmo ciclo de uso, favorece temas que já provaram força.

## 3. Reciclagem Inteligente

A cada execução, a função `reciclar_posts_antigos()` pode reativar posts publicados há mais de 60 dias.

Na reciclagem:

- O estudo permanece.
- O hook é zerado.
- A legenda é zerada.
- O prompt recebe `Modo de reciclagem: reciclagem`.
- A IA deve criar outro ângulo.

## 4. Estratégia de Exploração x Exploração

Use esta regra prática após 30 dias:

- 70% dos posts: pilares e subtemas vencedores.
- 20% dos posts: variações próximas dos vencedores.
- 10% dos posts: temas experimentais.

## 5. Diagnóstico por Pilar

A cada semana, rode:

```sql
select
  pilar,
  count(*) as posts,
  round(avg(engajamento_score), 2) as media_score,
  max(engajamento_score) as melhor_score
from posts
where status = 'postado'
group by pilar
order by media_score desc;
```

Decisão:

- Pilar com média alta: aumentar volume.
- Pilar com compartilhamento alto: transformar em série.
- Pilar com salvamento alto: vender produto da bio relacionado.
- Pilar com comentário alto e baixa curtida: conteúdo polarizante; usar com controle.

## 6. Ajuste do Prompt por Performance

Se salvamentos forem altos:

```text
Aumente a utilidade prática no final da legenda.
```

Se compartilhamentos forem altos:

```text
Aumente estranhamento e contraste no hook.
```

Se comentários forem altos:

```text
Use pergunta final curta, mas sem parecer caça-engajamento.
```

Se alcance for baixo:

```text
Reduza abstração. Use imagem mental concreta nos 3 primeiros segundos.
```

## 7. Métricas Mínimas para Decidir

Não conclua com menos de:

- 20 posts por pilar; ou
- 7 dias de publicação contínua; ou
- 1000 impressões totais no pilar.

Antes disso, qualquer conclusão é ruído.
