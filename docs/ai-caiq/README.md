# AI-CAIQ v1.1.0 — Ziggurat

An **audit trail, not a STAR filing**. Ziggurat is a locally-run developer CLI with no
customers, no hosted service and no network access; most of the 247 controls assume a
service and do not apply to it. This exists so that what *is* true about the tool is
written down with evidence somebody else can re-run, and so the gaps are visible instead
of implied.

## Status

**6 of 247 controls answered** (2 Yes, 4 No). The remaining **241 are UNASSESSED and left
EMPTY** in the workbook — *not* "No". Nobody has examined them against this subject yet.

| file | what it is |
|---|---|
| `ziggurat.yaml` | the source of record: per control, the answer, SSRM ownership, the implementation, and evidence with a runnable command or a file reference |
| `AI-CAIQ-ziggurat-v1.1.0.xlsx` | the yaml rendered into CSA's published workbook |

## The five rules this follows

1. **Every answer carries evidence that can be run.** A command with its observed output, a
   file, a test run — not prose.
2. **"No" is a legitimate answer.** There is no "Partial" in the AI-CAIQ vocabulary; a
   partial implementation is answered `No` with a `WHAT DOES EXIST:` clause.
3. **Unassessed is not No.** 241 controls are empty because nobody looked, and an empty cell
   says exactly that.
4. **A negative finding states where it looked.** See LOG-10, which names the two specific
   reasons the custody ledger cannot be claimed as protected audit records today.
5. **Name the right control.** IDs come from the workbook itself, and the domain prefixes
   are `A&A` and `I&S` — an `isalpha()` filter silently drops the ampersands.

## Reproducing the workbook

```bash
# the blank template is CSA's, is not redistributable, and is never modified in place
python3 ~/Software/rockin-robin/scripts/fill_ai_caiq.py \
  --template <your copy of AI_CAIQv1.1.0.xlsx> \
  --answers <ziggurat.yaml flattened to {control, answer, ssrm, implementation}> \
  --out docs/ai-caiq/AI-CAIQ-ziggurat-v1.1.0.xlsx
python3 ~/Software/rockin-robin/scripts/ai_caiq_coverage.py --workbook docs/ai-caiq/AI-CAIQ-ziggurat-v1.1.0.xlsx
python3 ~/rich-text/scripts/verify_ai_caiq_workbook.py --template <blank> --filled docs/ai-caiq/AI-CAIQ-ziggurat-v1.1.0.xlsx
```

The validator is not optional. `fill_ai_caiq.py` does **not** check SSRM values against the
template's eleven dropdown strings, despite its README saying it hard-errors on anything
else (moonsoup/rockin-robin#18) — SPIndlebox's own committed workbook was invalid for
exactly that reason (`OSP` instead of `Owned by OSP`) until 2026-09-17. Run the validator
before trusting a filled workbook.

## Scope boundary

The **toolchain** — SPIndlebox plus this plugin — is not a subject. Each tool answers for
itself: `spindlebox/docs/ai-caiq/spindlebox.yaml` covers the platform, and nothing here
borrows its evidence. Where a control is satisfied by the platform rather than by Ziggurat,
that belongs in the platform's assessment.
