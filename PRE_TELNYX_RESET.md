# Pre-Telnyx reset – voltooid

De code is teruggezet naar de staat vóór Telnyx (commit `f690e56`).

## Wat is gedaan

- ✅ Git reset naar pre-Telnyx
- ✅ Force push naar `origin/main`
- ✅ Render zal automatisch opnieuw deployen met de oude code

## Wat jij nog moet doen

### 1. Database downgraden in Supabase

1. Ga naar **Supabase** → het project dat Render gebruikt
2. Open **SQL Editor**
3. Voer het script uit: `scripts/downgrade_to_pre_telnyx.sql`

Dit script:
- Verwijdert de `orphaned_phone_numbers`-tabel
- Verwijdert `ai_worker_id` uit `crm_integrations`
- Zet de default van `call_recording_enabled` terug
- Past de alembic-versie aan naar 035
- **Zet Erik (en andere workers) op available**

### 2. Controleren

Na het script:

```sql
SELECT id, name, status, current_call_id FROM ai_workers;
```

Erik zou `status = 'available'` en `current_call_id = NULL` moeten hebben.

### 3. Testen

Bel naar je nummer. De AI zou nu moeten opnemen.

---

**Let op:** Render deployt automatisch bij een push. Controleer na de deploy of de app weer werkt.
