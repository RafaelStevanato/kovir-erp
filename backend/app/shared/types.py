from decimal import Decimal

# Valores financeiros, fiscais e monetários nunca devem usar float.
# Devem usar Decimal, representado pelo apelido Money.
Money = Decimal