# Data_reduction - Pipeline de Redução e Processamento OM

## Pré-requisitos
- Python 3.x
- Dependências: veja `requirements.txt`.
- Ambiente SAS e HEASoft inicializados:
  ```bash
  . /net/ASTRO/ricardomarzall/sas/sas_22/xmmsas_22.1.0-a8f2c2afa-20250304/initsas.sh
  heainit
  ```

## Estrutura dos scripts principais

- `main.py`: Pipeline principal. Faz download, extração e processamento OM.
- `lixo_1.py`: Exemplo de execução do omatt manualmente.
- `lixo_2.py`: Exemplo de execução do ommosaic manualmente.
- `omdataprep/`: Módulos utilitários e classes para download, extração, binning, mosaico, correção de Jupiter, etc.

## Como rodar o pipeline principal

1. Ative o ambiente SAS e HEASoft no terminal:
   ```bash
   . /net/ASTRO/ricardomarzall/sas/sas_22/xmmsas_22.1.0-a8f2c2afa-20250304/initsas.sh
   heainit
   ```
2. Edite o arquivo `main.py` para fornecer os parâmetros desejados:
   - **csv_file_path**: Caminho para o arquivo CSV contendo os OBSIDs a baixar.
   - **destination_directory**: Diretório onde os arquivos baixados e extraídos serão salvos.
   - **aioclient_path**: Caminho para o cliente de download (aioclient).
   - **start** e **end**: Índices (linha do CSV) indicando o intervalo de observações a baixar (ex: `start=1`, `end=10`).
   - **instname**: Nome do instrumento (ex: `OM`).
   - **filter_name**: Filtros desejados (ex: `UVW1 UVM2`).

   Exemplo de trecho editável em `main.py`:
   ```python
   csv_file_path = "/caminho/para/seu/arquivo.csv"
   destination_directory = "/caminho/para/destino"
   aioclient_path = "/caminho/para/aioclient"
   start = 1
   end = 10
   instname = "OM"
   filter_name = "UVW1 UVM2"
   ```
3. Execute o pipeline:
   ```bash
   python main.py
   ```
   Os logs serão salvos nos diretórios de destino e exibidos no terminal.

## Logging
- Todos os scripts utilizam o módulo `logging` do Python para registrar informações, avisos e erros.
- Os logs são salvos em arquivos como `log_download.txt`, `extract_log.txt` e exibidos no terminal.

## Documentação
- Todas as funções e classes principais possuem docstrings no padrão Google.
- Consulte os arquivos `.py` para detalhes de uso de cada classe/função.

## Exemplo de uso manual (omatt e ommosaic)
- Veja `lixo_1.py` e `lixo_2.py` para exemplos de execução manual de tarefas SAS específicas.

---

Dúvidas ou sugestões: abra uma issue ou consulte os comentários nos scripts.
