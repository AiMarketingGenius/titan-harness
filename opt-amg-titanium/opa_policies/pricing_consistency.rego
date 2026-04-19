package amg.titanium

import rego.v1

# AMG canonical pricing — enforced against client-facing surfaces.
# If input.file_prices is populated by the caller, compare against
# canonical set.

amg_tiers := {497, 797, 1497}
shield_tiers := {97, 197, 347}

canonical_prices := amg_tiers | shield_tiers

deny contains msg if {
    some f
    prices := input.file_prices[f]
    price := prices[_]
    not canonical_prices[price]
    msg := sprintf("pricing: file %s references non-canonical price $%d (canonical AMG: 497/797/1497; Shield: 97/197/347)", [f, price])
}
