# fixture: good_escape_clauses.md
# Expected: каждая из фраз ниже должна дать finding

## Требования к безопасности

Система должна шифровать данные, если возможно.
Данные передаются по защищённому каналу, где применимо.
Логи хранятся по возможности не менее 90 дней.
Резервное копирование выполняется при наличии технической возможности.
Проверка входных данных производится при необходимости.

## Требования к интеграции

The system shall support OAuth2 if feasible.
Authentication shall be enforced where applicable.
Encryption shall be applied where appropriate.
The module shall retry requests as needed.
Load balancing shall be configured if practical.
Failover shall be activated when necessary.
Logging shall be enabled where feasible.
