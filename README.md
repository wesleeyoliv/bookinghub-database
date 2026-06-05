# BookingHub - Trabalho Final de Banco de Dados

Projeto prático de Banco de Dados demonstrando concorrência (ACID), níveis de isolamento, recuperação de falhas (WAL/PITR) e otimização de consultas (Planos de Execução e Índices).

## Estrutura do Projeto

* `docker-compose.yml`: Infraestrutura (PostgreSQL 16 e API FastAPI).
* `postgresql.conf`: Configurações de performance, conexões e WAL (archive_mode).
* `schema.sql`: DDL completo do banco, incluindo índices de otimização criados na Parte 1.
* `seed.py`: Script de carga massiva (gera mais de 10.000 registros de aeroportos, voos, hotéis, quartos e clientes).
* `api/`: Código-fonte da API Python (FastAPI + psycopg2). Contém endpoints de consultas e reservas.
* `testes/`: Scripts para validação de concorrência, deadlocks, política de retry e nível de isolamento.
* `backup/`: Scripts para testar backup lógico (`pg_dump`) e físico/PITR (`pg_basebackup`).
* `relatorio.pdf`: Relatório final documentando todo o projeto.

## Pré-requisitos

* Docker e Docker Compose instalados.
* Python 3.10+ instalado localmente (para rodar o gerador de dados e os testes).
* Instalar os pacotes necessários:
  ```bash
  pip install psycopg2-binary requests faker
  ```

## 1. Como executar o projeto localmente

1. **Subir os containers (Banco e API)**
   Na raiz deste repositório, onde está o `docker-compose.yml`, rode:
   ```bash
   docker compose up -d
   ```
   *O PostgreSQL subirá na porta **5433** (para não conflitar com bancos locais) e a API na porta **8001**.*

2. **Acompanhar logs da inicialização**
   ```bash
   docker compose logs -f
   ```

3. **Popular o banco de dados**
   Rode o script `seed.py` para injetar os registros no banco:
   ```bash
   python seed.py
   ```

4. **Acessar a documentação interativa da API**
   Abra o navegador em: [http://localhost:8001/docs](http://localhost:8001/docs)

## 2. Testando a API e Concorrência

Você pode testar a API acessando o Swagger no navegador (link acima) ou rodar os scripts de testes que preparamos:

1. **Teste Automatizado da API:**
   ```bash
   python testes/testar_api.py
   ```
   (Chama as rotas de GET, tenta criar pacote com savepoints, testa histórico e falha proposital).

2. **Teste de Overbooking (Concorrência pesada):**
   ```bash
   python testes/teste_overbooking.py
   ```

3. **Teste de Double Booking em Hotel:**
   ```bash
   python testes/teste_conflito_hotel.py
   ```

4. **Teste de Nível de Isolamento (Read Committed vs Serializable):**
   ```bash
   python testes/teste_isolamento.py
   ```

5. **Teste de Falha e Rollback (Transação interrompida):**
   ```bash
   python testes/teste_falha_transacao.py
   ```

## 3. Testando Backups e Point-in-Time Recovery (PITR)

O diretório `backup/` contém dois scripts:

1. **Backup Lógico (`pg_dump` e `pg_restore`):**
   ```bash
   python backup/teste_backup_logico.py
   ```

2. **Backup Físico e Point-in-Time Recovery:**
   *Este script realiza o `pg_basebackup`, anota o timestamp de recuperação, provoca o crash do banco e levanta novamente usando os arquivos WAL (Write-Ahead Logging).*
   ```bash
   python backup/teste_pitr.py
   ```

> **Aviso:** Os scripts de PITR param o container e injetam configurações no `/var/lib/postgresql/data`. Certifique-se de que os containers subiram normalmente antes de executá-los.
