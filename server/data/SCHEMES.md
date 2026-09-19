# Scheme data format (schema v1)

Every scheme is one JSON object. The same shape is used in `schemes.json` files and in MongoDB (`urimai.schemes`).
The schema is enforced by [`app/catalogue/schema.py`](../app/catalogue/schema.py); a machine-readable copy for
editors and tools is [`scheme.schema.json`](scheme.schema.json) (regenerate with `python -m app.catalogue.schema`).

- Keys are **case-sensitive**, and **unknown keys are errors**, so a typo like `"eligibilty"` is caught.
- Text shown to users is a **`Text` object**: `{"en": "...", "ta": "...", "hi": "..."}`. `en` is required;
  missing `ta` / `hi` fall back to English.

## A complete example

(Based on the real `kmut` record; the `other` line is added to illustrate the format.)

```json
{
  "schema_version": 1,
  "id": "kmut",
  "status": "active",
  "level": "state",
  "state": "TN",
  "category": ["women", "income_support"],
  "name": { "en": "Kalaignar Magalir Urimai Thogai", "ta": "கலைஞர் மகளிர் உரிமைத் தொகை" },
  "benefit": {
    "summary": { "en": "₹1,000 a month to women heads of family", "ta": "குடும்பத் தலைவிகளுக்கு மாதம் ₹1,000" },
    "annual_cash_value_inr": 12000
  },
  "eligibility": {
    "all":  [ { "field": "gender", "op": "eq", "value": "female" },
              { "field": "age", "op": "gte", "value": 21 },
              { "field": "is_head_of_family", "op": "is_true" },
              { "field": "annual_family_income", "op": "lte", "value": 250000 } ],
    "none": [ { "field": "is_govt_employee", "op": "is_true" },
              { "field": "is_income_tax_payer", "op": "is_true" } ],
    "other": [ { "en": "Family owns less than 5 acres of wet land or 10 acres of dry land" } ]
  },
  "documents": ["aadhaar", "ration_card", "bank_passbook", "electricity_bill"],
  "application": {
    "mode": "both",
    "where": { "en": "Special camps / ration shop area, or kmut.tn.gov.in" },
    "url": "https://kmut.tn.gov.in/",
    "steps": { "en": ["Collect the form at your ration shop or camp", "Submit it at the camp"] }
  },
  "source": { "url": "https://kmut.tn.gov.in/", "origin": "manual" },
  "verification": { "status": "unverified", "last_verified": null },
  "mutually_exclusive_with": ["ignoaps", "ignwps", "igndps"]
}
```

## Fields

| Key | Type | Required | What it is |
|---|---|---|---|
| `schema_version` | `1` | yes | Format version. Always `1` for now |
| `id` | text | yes | Unique id: lowercase letters, digits, `_`; 2–64 chars, e.g. `pm_kisan`. Never reuse or change it |
| `status` | `active` \| `closed` | no (`active`) | `closed` schemes are kept but never shown |
| `level` | `central` \| `state` | yes | Who runs it |
| `state` | state code | state schemes only | e.g. `TN`. Must be absent for central schemes. The server adds "Lives in <state>" as a rule automatically |
| `category` | list of categories | yes (≥1) | See [Categories](#categories). Used for search and question planning |
| `name` | Text | yes | Scheme name as people know it |
| `aliases` | list of text | no | Other names people use, any language: abbreviations (`KMUT`), short forms (`PM Kisan`), common spellings (`Tamil Puthalvan`). Up to 20, each 1–80 chars. Scheme search matches them, so "KMUT documents" finds the right scheme |
| `benefit.summary` | Text | yes | One line: what the person gets |
| `benefit.annual_cash_value_inr` | number ≥ 0 | no (`0`) | Cash per year, used to rank schemes and total the benefit. `0` for non-cash benefits |
| `benefit.cover_highlight` | Text | no | Headline for non-cash benefits, e.g. "₹5 lakh health cover" |
| `eligibility` | object | yes | Rules, see [Eligibility](#eligibility) |
| `documents` | list | no | Documents to apply, see [Documents](#documents) |
| `application.mode` | `online` \| `offline` \| `both` | yes | How to apply |
| `application.where` | Text | one of where/url/steps | Office or website in words |
| `application.url` | URL | one of where/url/steps | Where to apply online |
| `application.steps` | `{"en": [..], "ta": [..], "hi": [..]}` | one of where/url/steps | Steps in order |
| `source.url` | URL | yes | Official page the details come from (shown to users) |
| `source.origin` | text | no | Where this record came from: `manual`, `myscheme.gov.in`, … |
| `source.external_id` | text | no | The scheme's id at the origin, so re-imports update instead of duplicating |
| `verification.status` | `draft` \| `unverified` \| `verified` | no (`draft`) | `draft`: stored, **never shown**. `unverified`: shown with a "being verified" note. `verified`: checked against the official source |
| `verification.last_verified` | `YYYY-MM-DD` | when `verified` | Date it was checked |
| `verification.verified_by` | text | no | Who checked it |
| `verification.notes` | text | no | Reviewer notes |
| `mutually_exclusive_with` | list of ids | no | Schemes a person can't get together with this one (e.g. two pensions). Every id must exist |

### Added by the server (don't write these)

| Key | What it is |
|---|---|
| `_id` | MongoDB's document id |
| `updated_at` | When the seed command last wrote the scheme |

## Eligibility

```json
"eligibility": { "all": [...], "any": [...], "none": [...], "other": [...] }
```

| Block | Meaning |
|---|---|
| `all` | **Every** rule must pass |
| `any` | **At least one** rule must pass |
| `none` | **None** of these may be true (exclusions, e.g. income-tax payers) |
| `other` | Requirements the bot can't check from the conversation, as Text. Shown to the user as 📋 "please check"; they never change the result |

At least one rule in `all` / `any` / `none` is required: a scheme with only `other` text would look likely for everyone.
The result for each person is **likely** (all rules pass), **need info** (some unknown) or **not eligible** (a rule fails).
Unknown never counts as "no".

A **rule** is `{"field": ..., "op": ..., "value": ...}`, plus an optional `"text"` (Text) to override the
auto-generated rule description shown to users.

| op | value | Example |
|---|---|---|
| `is_true` / `is_false` | none | `{"field": "has_bpl_ration_card", "op": "is_true"}` |
| `eq` / `ne` | one value | `{"field": "gender", "op": "eq", "value": "female"}` |
| `in` / `not_in` | list | `{"field": "caste_category", "op": "in", "value": ["sc", "st"]}` |
| `lt` / `lte` / `gt` / `gte` | number | `{"field": "age", "op": "gte", "value": 60}` |
| `between` | `[low, high]` inclusive | `{"field": "age", "op": "between", "value": [18, 40]}` |

The value must fit the field: numbers for number fields, one of the listed values for choice fields, and
yes/no fields only take `is_true` / `is_false`.

### Profile fields a rule can use

| Field | Type | Allowed values | Ops |
|---|---|---|---|
| `name` | text | text | eq, ne, in, not_in |
| `age` | int | 0–120 | all number ops |
| `gender` | choice | `female`, `male`, `transgender` | eq, ne, in, not_in |
| `state` | state code | see [State codes](#state-codes) | eq, ne, in, not_in |
| `district` | text | district name in English | eq, ne, in, not_in |
| `residence` | choice | `rural`, `urban` | eq, ne, in, not_in |
| `marital_status` | choice | `single`, `married`, `widowed`, `divorced`, `separated` | eq, ne, in, not_in |
| `is_head_of_family` | yes/no | | is_true, is_false |
| `annual_family_income` | int | ₹ per year, 0–10,00,00,000 | all number ops |
| `occupation` | choice | `farmer`, `agri_labourer`, `daily_wage_labourer`, `construction_worker`, `street_vendor`, `artisan`, `domestic_worker`, `fisherman`, `self_employed`, `small_business`, `salaried_private`, `salaried_govt`, `student`, `unemployed`, `homemaker`, `retired`, `other`; with `in`/`not_in` also `@UNORGANISED` (any unorganised-sector job) | eq, ne, in, not_in |
| `caste_category` | choice | `general`, `obc`, `bc`, `mbc`, `sc`, `st` | eq, ne, in, not_in |
| `is_minority` | yes/no | | is_true, is_false |
| `has_bpl_ration_card` | yes/no | priority (PHH/AAY) ration card | is_true, is_false |
| `owns_agri_land` | yes/no | | is_true, is_false |
| `land_acres` | number | 0–1,00,000 | all number ops |
| `has_pucca_house` | yes/no | | is_true, is_false |
| `owns_house` | yes/no | | is_true, is_false |
| `has_lpg_connection` | yes/no | | is_true, is_false |
| `has_electricity_connection` | yes/no | | is_true, is_false |
| `has_bank_account` | yes/no | | is_true, is_false |
| `is_income_tax_payer` | yes/no | | is_true, is_false |
| `is_govt_employee` | yes/no | | is_true, is_false |
| `is_epfo_member` | yes/no | | is_true, is_false |
| `has_disability` | yes/no | | is_true, is_false |
| `disability_percent` | int | 0–100 | all number ops |
| `is_pregnant` | yes/no | | is_true, is_false |
| `education_level` | choice (ordered) | `none` < `primary` < `8th` < `10th` < `12th` < `iti` < `diploma` < `degree` < `postgrad` | eq, ne, in, not_in, and lt/lte/gt/gte by level |
| `is_student_higher_ed` | yes/no | | is_true, is_false |
| `studied_in_govt_school` | yes/no | | is_true, is_false |
| `wants_to_start_business` | yes/no | | is_true, is_false |
| `is_first_gen_entrepreneur` | yes/no | | is_true, is_false |
| `has_girl_child_under_10` | yes/no, from children | | is_true, is_false |
| `has_girl_child_in_govt_school_14_17` | yes/no, from children | | is_true, is_false |
| `has_boy_child_in_govt_school_14_17` | yes/no, from children | | is_true, is_false |
| `caste_is_sc_st` | yes/no, from caste | | is_true, is_false |

A requirement that none of these fields can express goes in `other` as text. If many schemes need the same new
fact (e.g. "is a registered fisherman"), add it as a profile field in `app/domain/fields.py` with its question,
and then it can be used in rules and the bot will ask about it.

## Documents

Each entry is either a **standard id**:

`aadhaar`, `ration_card`, `income_certificate`, `community_certificate`, `age_proof`, `bank_passbook`,
`land_records`, `death_certificate_spouse`, `disability_certificate`, `school_certificate`,
`college_admission_proof`, `pregnancy_registration`, `birth_certificate_child`, `photo`, `residence_proof`,
`project_report`, `educational_certificate`, `electricity_bill`, `vending_certificate`

or a **custom document** for anything else:

```json
{ "id": "fishing_licence", "label": { "en": "Fishing licence", "ta": "மீன்பிடி உரிமம்" } }
```

Standard ids are shared across schemes, so the bot can say "Aadhaar: needed for 7 schemes". Use them whenever one fits.

## Categories

`agriculture`, `banking`, `business`, `child_welfare`, `disability`, `education`, `employment`, `energy`,
`fisheries`, `food_security`, `health`, `housing`, `income_support`, `insurance`, `legal_aid`, `livestock`,
`maternity`, `minority_welfare`, `pension`, `savings`, `sc_st_welfare`, `senior_citizens`, `skill_development`,
`sports_culture`, `transport`, `water_sanitation`, `women`

## State codes

States: `AP` Andhra Pradesh, `AR` Arunachal Pradesh, `AS` Assam, `BR` Bihar, `CG` Chhattisgarh, `GA` Goa,
`GJ` Gujarat, `HR` Haryana, `HP` Himachal Pradesh, `JH` Jharkhand, `KA` Karnataka, `KL` Kerala,
`MP` Madhya Pradesh, `MH` Maharashtra, `MN` Manipur, `ML` Meghalaya, `MZ` Mizoram, `NL` Nagaland, `OD` Odisha,
`PB` Punjab, `RJ` Rajasthan, `SK` Sikkim, `TN` Tamil Nadu, `TG` Telangana, `TR` Tripura, `UP` Uttar Pradesh,
`UK` Uttarakhand, `WB` West Bengal.
Union territories: `AN` Andaman & Nicobar, `CH` Chandigarh, `DH` Dadra & Nagar Haveli and Daman & Diu,
`DL` Delhi, `JK` Jammu & Kashmir, `LA` Ladakh, `LD` Lakshadweep, `PY` Puducherry.

## Loading schemes: start small

```bash
cd server
python -m app.catalogue.seed --dry-run my_schemes.json   # 1. check only; lists every problem, writes nothing
python -m app.catalogue.seed test_5.json                 # 2. load a few, try them in the bot
python -m app.catalogue.seed my_schemes.json             # 3. load the rest (re-running updates by id)
```

Invalid schemes are listed with the reason and skipped; the valid ones are written. Each load also updates
scheme search (`scheme_chunks` and its Atlas indexes); `--no-chunks` skips that. Add `--strict` to write
nothing if any scheme is invalid. Import new schemes as `"verification": {"status": "draft"}` to store them
without showing them, then change them to `unverified` or `verified` once reviewed.
