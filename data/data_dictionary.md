# Dicionário de Dados (FAIR — Interoperable)

**Projeto:** Estudantes da rede pública por nível de ensino nas Regiões Administrativas do Rio de Janeiro (2000 × 2010)
**Fonte primária:** Instituto Pereira Passos (IPP) — Armazém de Dados / [Data.Rio](https://www.data.rio/), *Tabela 892 — Número de estudantes da rede pública por nível de ensino, segundo as Regiões Administrativas — 2000/2010*. Dados originais: IBGE, Censos Demográficos 2000 e 2010 (questionário da **amostra**).
**Licença dos dados processados:** CC-BY 4.0 (ver `LICENSE-CC-BY-4.0.md`).
**Codificação de todos os arquivos texto:** UTF-8. Separador decimal nos CSV: ponto (`.`). Separador de campo: vírgula (`,`).

---

## 1. Dado bruto — `data/raw/tabela_892_estudantes_rede_publica_RA_2000_2010.xls`

| Atributo | Descrição |
|---|---|
| Formato | Excel 97-2003 (`.xls`, BIFF8), 2 abas: `2000` e `2010` |
| SHA-256 | `df4717c72e03073f4ce63ef5d4b7925c631aeb73451d2e5195b26e5f9e063046` |
| Granularidade | 1 linha = 1 Região Administrativa (RA) + 1 linha de total do município; 1 coluna = 1 nível de ensino |
| Cobertura | 2000: 32 RA + município; 2010: 33 RA + município (RA XXXI Vigário Geral só aparece em 2010) |
| Unidade | pessoas (estudantes) que frequentavam escola/creche/curso da **rede pública**, segundo a RA de **residência** |
| Particularidades | cabeçalho em 3 linhas mescladas; títulos e notas nas linhas superiores/inferiores; níveis de ensino diferentes entre os anos; valores de 2010 são estimativas ponderadas da amostra (com casas decimais) |
| Marcadores | `...` = dado numérico não disponível (aba 2000) · `-` = zero absoluto, não resultante de arredondamento (aba 2010) |

O arquivo bruto **nunca é modificado**: o pipeline (`src/etl.py`) lê, transforma em memória e grava apenas em `data/processed/`.

---

## 2. `data/processed/estudantes_ra_nivel_longo.{parquet,csv.gz}` — tabela principal (formato longo / *tidy*)

Granularidade: **ano × território × nível de ensino original** (837 linhas).

| Variável | Tipo primitivo | Formato / domínio | Significado |
|---|---|---|---|
| `ano` | int16 | `2000`, `2010` | Ano de referência do Censo Demográfico |
| `nivel_territorial` | category | `municipio`, `regiao_administrativa` | Distingue a linha de total do município das RA |
| `ra_codigo` | int16 | 0–34 | Número da RA convertido do algarismo romano (0 = município) |
| `ra_romano` | string | ex.: `XVIII` | Código romano original da RA (vazio para o município) |
| `ra_nome` | string | ex.: `Campo Grande` | Nome da RA padronizado (espaços removidos; grafias corrigidas: `IIha do Governador`→`Ilha do Governador`, `SantaTeresa`→`Santa Teresa`) |
| `area_planejamento` | category | `AP1`…`AP5`, `Total` | Área de Planejamento à qual a RA pertence (derivada) |
| `rotulo_bruto` | string | texto | Rótulo exatamente como aparece no arquivo bruto (rastreabilidade) |
| `nivel_original` | category | 13 níveis (2000) / 12 níveis (2010) | Nível de ensino conforme publicado, com nome padronizado |
| `nivel_harmonizado` | category | ver tabela 6 | Nível comparável entre 2000 e 2010 |
| `etapa` | category | ver tabela 6 | Agrupamento analítico do nível de ensino |
| `comparavel_2000_2010` | bool | `True`/`False` | `False` para níveis existentes em apenas um dos anos (Pré-vestibular, Especialização) |
| `estudantes` | float64 | ≥ 0; `NaN` se indisponível | Número de estudantes (2010 = estimativa ponderada, não inteira) |
| `status_dado` | category | `observado`, `nao_disponivel`, `zero_absoluto` | Como o valor foi obtido a partir da célula bruta |
| `valor_bruto` | string | texto | Conteúdo original da célula (ex.: `...`, `-`, `572090`) |
| `total_publicado_ra` | float64 | ≥ 0 | Coluna "Total" publicada para o território |

## 3. `data/processed/estudantes_ra_etapa.{parquet,csv.gz}`

Granularidade: **ano × território × etapa**, considerando **apenas níveis comparáveis**.

| Variável | Tipo | Significado |
|---|---|---|
| `ano`, `ra_codigo`, `ra_nome`, `area_planejamento` | — | Como na tabela principal |
| `etapa` | category | Educação Infantil, Ensino Fundamental, Ensino Médio, Educação de Jovens e Adultos, Ensino Superior |
| `estudantes` | float64 | Soma dos níveis da etapa |
| `total_territorio` | float64 | Total comparável de estudantes no território/ano |
| `participacao_pct` | float64 | `100 × estudantes / total_territorio` (%) |

## 4. `data/processed/variacao_ra_2000_2010.{parquet,csv.gz}`

Granularidade: **RA** (+ 1 unidade territorial compatibilizada).

| Variável | Tipo | Significado |
|---|---|---|
| `ra_codigo`, `ra_nome`, `area_planejamento` | — | Identificação da RA (`1131` = unidade compatibilizada) |
| `estudantes_2000`, `estudantes_2010` | float64 | Total comparável de estudantes em cada ano |
| `unidade_compatibilizada` | bool | `True` para *Penha + Vigário Geral* (soma das RA XI e XXXI), criada porque Vigário Geral não existe na tabela de 2000 |
| `variacao_abs` | float64 | `estudantes_2010 − estudantes_2000` |
| `variacao_pct` | float64 | `100 × (estudantes_2010 / estudantes_2000 − 1)` (%) |
| `taxa_anual_pct` | float64 | Taxa geométrica média anual: `100 × ((e2010/e2000)^(1/10) − 1)` (% a.a.) |
| `participacao_municipio_{ano}_pct` | float64 | Participação da RA no total do município (% — calculada sobre as RA originais) |

## 5. `data/processed/indicador_ensino_superior_ra.{parquet,csv.gz}`

| Variável | Tipo | Significado |
|---|---|---|
| `ano`, `ra_codigo`, `ra_nome`, `area_planejamento` | — | Identificação |
| `estudantes_superior` | float64 | Estudantes de graduação + mestrado/doutorado da rede pública |
| `pct_superior` | float64 | `100 × estudantes_superior / total comparável da RA` (%) — "peso do ensino superior" |

## 6. Tabela de harmonização dos níveis de ensino

| Etapa | Nível harmonizado | 2000 (original) | 2010 (original) | Comparável |
|---|---|---|---|---|
| Educação Infantil | Creche | Creche | Creche | sim |
| Educação Infantil | Pré-escola | Pré-escola | Pré-escola | sim |
| Educação Infantil | Classe de alfabetização | Classe de alfabetização | Classe de alfabetização | sim |
| Ensino Fundamental | Fundamental regular | Regular seriado + Regular não seriado | Regular | sim |
| Ensino Médio | Médio regular | Regular seriado + Regular não seriado | Regular | sim |
| Educação de Jovens e Adultos | Alfabetização de adultos | Alfabetização de adultos | Alfabetização de adultos | sim |
| Educação de Jovens e Adultos | Fundamental supletivo | Supletivo | Supletivo | sim |
| Educação de Jovens e Adultos | Médio supletivo | Supletivo | Supletivo | sim |
| Ensino Superior | Superior graduação | Ensino superior – Graduação | Ensino superior – Graduação | sim |
| Ensino Superior | Mestrado/doutorado | Mestrado ou Doutorado | Mestrado + Doutorado | sim |
| Ensino Superior | Especialização | — | Especialização de nível superior | **não** |
| Pré-vestibular | Pré-vestibular | Pré-vestibular | — | **não** |

## 7. Regras de tratamento de valores

| Situação | Ocorrências | Tratamento | Justificativa |
|---|---|---|---|
| `...` (não disponível, 2000) | 11 células (Paquetá: 7; Rocinha, Jacarezinho, Complexo do Alemão e Cidade de Deus: mestrado/doutorado) | `NaN`, **sem imputação**; somas usam `min_count=1` | O total publicado de cada RA é igual à soma das parcelas disponíveis (diferença máxima = 0,000%), logo essas células não contribuem para os totais |
| `-` (zero absoluto, 2010) | 15 células | `0.0` | Definição explícita da nota do IBGE |
| Decimais em 2010 | todas as células | mantidos em `float64`; arredondados apenas na apresentação | São expansões da amostra; arredondar no ETL introduziria erro |
| Soma das RA × total do município | 2000: −0,019%; 2010: 0,000% | apenas reportado em `relatorio_qualidade.json` | Diferença atribuída à amostragem (nota (1) da aba 2000) |

## 8. `data/processed/relatorio_qualidade.json`

Relatório automático de validação gerado a cada execução do pipeline: número de RA por ano, contagem de `status_dado`, soma das RA × total municipal, diferença máxima entre parcelas e total publicado, lista das células indisponíveis e RA presentes em apenas um dos anos.
