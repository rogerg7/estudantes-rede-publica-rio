# Estudantes da rede pública por nível de ensino nas Regiões Administrativas do Rio de Janeiro (2000 × 2010)

[![Artigo](https://img.shields.io/badge/artigo-GitHub%20Pages-2a78d6)](https://rogerg7.github.io/estudantes-rede-publica-rio/)
[![Python](https://img.shields.io/badge/python-3.13-2a78d6)](https://www.python.org/)
[![Código: MIT](https://img.shields.io/badge/c%C3%B3digo-MIT-1baf7a)](LICENSE)
[![Dados e texto: CC BY 4.0](https://img.shields.io/badge/dados%20%26%20texto-CC%20BY%204.0-1baf7a)](LICENSE-CC-BY-4.0.md)
[![FAIR](https://img.shields.io/badge/FAIR-F%C2%B7A%C2%B7I%C2%B7R-eb6834)](#princípios-fair)
[![Fonte](https://img.shields.io/badge/fonte-IBGE%20%2F%20Data.Rio-52514e)](https://www.data.rio/)

| | |
|---|---|
| **Autoria** | Roger Gomes e Rodrigo Lorenzatto — Bacharelado em Sistemas de Informação |
| **Instituição** | Universidade La Salle — Rio de Janeiro |
| **Disciplina** | Linguagem de Programação (Análise e Visualização de Dados com Python) — 6º período |
| **Semestre** | 2026.2 |
| **Artigo (HTML)** | <https://rogerg7.github.io/estudantes-rede-publica-rio/> |
| **Repositório** | <https://github.com/rogerg7/estudantes-rede-publica-rio> |

---

## Resumo executivo

Este projeto analisa como mudou, entre os Censos de **2000** e **2010**, o número de estudantes da **rede pública** do Município do Rio de Janeiro por **nível de ensino** e por **Região Administrativa (RA)**. Um pipeline determinístico em Python lê a Tabela 892 do Armazém de Dados (IPP/Data.Rio), trata o cabeçalho mesclado e os marcadores do IBGE (`...` e `-`), harmoniza os níveis de ensino dos dois censos, compatibiliza a criação da RA Vigário Geral e gera tabelas abertas (Parquet/CSV.gz) e um artigo web interativo.

**Principais achados**

- A rede pública passou de **1,00 milhão** para **1,12 milhão** de estudantes (**+12,0%**), mas o **ensino fundamental regular caiu 9,4%**, enquanto **creche (+119%)**, **EJA/supletivo (+230%)** e **ensino superior (+43%)** cresceram.
- A distribuição entre as RA ficou **levemente menos concentrada** (Gini 0,436 → 0,399). Barra da Tijuca (+71,5%), Portuária (+68,2%) e Rocinha (+65,4%) tiveram o maior crescimento relativo.
- O peso do ensino superior público varia de **1,2% (Complexo do Alemão) a 45,0% (Botafogo)** em 2010; a hierarquia entre as RA é praticamente a mesma de 2000 (Spearman ρ = 0,94) e a distância absoluta entre os extremos aumentou.

**Palavras-chave:** educação pública; Censo Demográfico; Regiões Administrativas; Rio de Janeiro; desigualdade territorial; ciência de dados aberta.

---

## Perguntas de pesquisa

- **RQ1** — Como variou a composição da população estudantil da rede pública por etapa de ensino entre 2000 e 2010?
- **RQ2** — Como os estudantes se distribuem entre as RA e onde se concentraram o crescimento e a retração?
- **RQ3** — Existe desigualdade territorial no peso do ensino superior público entre as RA e ela se reduziu no período?

---

## Fonte dos dados

| Item | Valor |
|---|---|
| Tabela | **Tabela 892** — Número de estudantes da rede pública por nível de ensino, segundo as Regiões Administrativas — 2000/2010 |
| Publicador | Instituto Pereira Passos (IPP) — Armazém de Dados / Data.Rio — <https://www.data.rio/> |
| Produtor | IBGE — Censos Demográficos 2000 e 2010 (amostra) |
| Arquivo bruto | [`data/raw/tabela_892_estudantes_rede_publica_RA_2000_2010.xls`](data/raw/) (SHA-256 `df4717c7…063046`) |
| Dicionário de dados | [`data/data_dictionary.md`](data/data_dictionary.md) |

---

## Estrutura do repositório

```
estudantes-rede-publica-rio/
├── README.md                  # Este arquivo
├── LICENSE                    # MIT (código)
├── LICENSE-CC-BY-4.0.md       # CC BY 4.0 (dados processados, figuras e texto)
├── requirements.txt           # Dependências congeladas (pip freeze)
├── .gitignore
├── data/
│   ├── raw/                   # Dado bruto original (.xls) — nunca é alterado
│   ├── processed/             # Parquet + CSV.gz + relatorio_qualidade.json
│   └── data_dictionary.md     # Metadados e dicionário de variáveis
├── notebooks/
│   └── analise_exploratoria.ipynb   # Exploração, validação e estatísticas (executado)
├── src/
│   ├── __init__.py
│   ├── etl.py                 # Extração, limpeza, harmonização, validação e métricas
│   └── visualizacoes.py       # Figuras estáticas (Matplotlib) e interativas (Plotly)
└── docs/                      # Publicado via GitHub Pages
    ├── index.html             # Artigo científico em HTML5
    └── assets/                # Figuras PNG + gráficos interativos (HTML/Plotly)
```

---

## Como reproduzir

Requisitos: **Python 3.13** e Git. Nenhuma credencial ou API paga é necessária.

```bash
# 1. Clonar
git clone https://github.com/rogerg7/estudantes-rede-publica-rio.git
cd estudantes-rede-publica-rio

# 2. Ambiente virtual com as versões congeladas
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Pipeline ETL  -> data/processed/
python -m src.etl

# 4. Figuras       -> docs/assets/
python -m src.visualizacoes

# 5. (opcional) Re-executar o notebook de ponta a ponta
jupyter nbconvert --to notebook --execute --inplace notebooks/analise_exploratoria.ipynb

# 6. Visualizar o artigo localmente
python -m http.server -d docs 8000   # abra http://localhost:8000
```

O pipeline é determinístico: as mesmas entradas geram exatamente os mesmos arquivos de saída e o mesmo `relatorio_qualidade.json`.

---

## Princípios FAIR

| Princípio | Como é atendido |
|---|---|
| **Findable** | README com resumo, palavras-chave, autoria, instituição e semestre; link para a fonte original (Data.Rio); metadados também no `<head>` do artigo (Dublin Core / `citation_*`) |
| **Accessible** | Repositório público, artigo aberto no GitHub Pages, scripts sem autenticação; dado bruto versionado no repositório (< 1 MB) |
| **Interoperable** | `data/data_dictionary.md` com tipo, formato e significado de cada variável; dados em Parquet e CSV.gz (UTF-8) |
| **Reusable** | Licenças MIT (código) e CC BY 4.0 (dados/texto); `requirements.txt` congelado; pipeline rastreável (`valor_bruto`, `status_dado`, relatório de qualidade) |

---
