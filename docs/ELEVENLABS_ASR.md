# ElevenLabs spraakherkenning (ASR) – handleiding

Deze handleiding beschrijft hoe je de spraakherkenning van ElevenLabs Conversational AI kunt verbeteren. Betere transcriptie leidt tot minder misverstanden en een soepelere klantenservice.

## Waar vind je de instellingen?

Ga in het ElevenLabs-dashboard naar:

**Agent → Conversation config → ASR** (of Speech-to-Text)

Niet alle ElevenLabs-plannen tonen ASR-configuratie. Als je deze sectie niet ziet, controleer de agent-API of neem contact op met ElevenLabs.

---

## 1. ASR Keywords (vocabulary biasing)

**Wat het doet:** Verhoogt de herkenningskans van specifieke woorden die vaak verkeerd worden getranscribeerd.

**Hoe te gebruiken:**
- Voeg een lijst **keywords** toe (max. ~100 woorden, elk tot ~50 tekens)
- Voorbeelden:
  - Bedrijfsnaam en productnamen
  - Veelvoorkomende Nederlandse achternamen (De Vries, Van den Berg, Bakker, etc.)
  - Domeinspecifieke termen (productnamen, diensten)

**Tip:** Voeg woorden toe waarvan je merkt dat ze vaak verkeerd worden herkend in gesprekken.

---

## 2. ASR-provider

**Opties:** `elevenlabs`, `scribe_realtime`, `scribe_v2_turbo`

**Aanbeveling:** Test `scribe_v2_turbo` als die beschikbaar is. Deze provider kan betere transcriptie geven, vooral bij:
- Achtergrondgeluid
- Accenten en dialecten
- Namen en codes

---

## 3. Spelling patience

**Waar:** Agent settings → Turn/Conversation config

**Instelling:** `SpellingPatience` – "Controls if the agent should be more patient when user is spelling numbers and named entities."

**Aanbeveling:** Zet op `auto` of aan. Dit helpt wanneer klanten:
- Hun naam spellen (bijv. "H-O-W-E, Howe")
- Een bevestigingscode of ordernummer opgeven
- Telefoonnummers dicteren

---

## 4. Taal

**Waar:** Agent settings → Language

**Controleer:** Taal staat op **Dutch** (of het juiste Nederlands-preset). Dit optimaliseert de transcriptie voor het Nederlands.

---

## Overzicht

| Instelling        | Aanbeveling                          |
|-------------------|--------------------------------------|
| ASR Keywords      | Voeg bedrijfsnaam, namen, termen toe |
| ASR Provider      | Test `scribe_v2_turbo`               |
| Spelling patience | `auto` of aan                        |
| Taal              | Dutch                                |

---

## Gerelateerd

De prompt bevat ook instructies voor de AI om bij onduidelijke transcriptie om herhaling of spelling te vragen. Zie de system prompts "Bij onbegrip" en "Few-shot voorbeelden" in het admin-panel.
