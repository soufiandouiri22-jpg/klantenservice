"""
klantenservice.ai - KVK (Kamer van Koophandel) Endpoints
Proxy for the KVK Handelsregister API to search Dutch companies.
"""
import httpx
import logging
from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class KvkAddress(BaseModel):
    straatnaam: Optional[str] = None
    huisnummer: Optional[int] = None
    postcode: Optional[str] = None
    plaats: Optional[str] = None


class KvkSearchResult(BaseModel):
    kvk_nummer: str
    naam: str
    adres: Optional[KvkAddress] = None
    type: Optional[str] = None
    actief: Optional[str] = None


class KvkSearchResponse(BaseModel):
    resultaten: List[KvkSearchResult]
    totaal: int


@router.get("/zoeken", response_model=KvkSearchResponse)
async def search_kvk(
    naam: str = Query(..., min_length=2, max_length=200, description="Bedrijfsnaam om te zoeken"),
    limit: int = Query(5, ge=1, le=20),
):
    """
    Search the KVK Handelsregister by company name.
    Returns matching companies with their KVK number and address.
    No authentication required (public endpoint for registration).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.KVK_API_URL}/zoeken",
                params={
                    "naam": naam,
                    "resultatenPerPagina": limit,
                },
                headers={
                    "apikey": settings.KVK_API_KEY,
                },
            )

        if response.status_code == 404 or response.status_code == 204:
            return KvkSearchResponse(resultaten=[], totaal=0)

        if response.status_code != 200:
            logger.warning(f"KVK API returned status {response.status_code}: {response.text[:200]}")
            return KvkSearchResponse(resultaten=[], totaal=0)

        data = response.json()
        resultaten = []

        for item in data.get("resultaten", []):
            # Parse address from nested structure
            adres = None
            adres_data = item.get("adres", {})
            binnenlands = adres_data.get("binnenlandsAdres")
            if binnenlands:
                adres = KvkAddress(
                    straatnaam=binnenlands.get("straatnaam"),
                    huisnummer=binnenlands.get("huisnummer"),
                    postcode=binnenlands.get("postcode"),
                    plaats=binnenlands.get("plaats"),
                )

            resultaten.append(KvkSearchResult(
                kvk_nummer=item.get("kvkNummer", ""),
                naam=item.get("naam", ""),
                adres=adres,
                type=item.get("type"),
                actief=item.get("actief"),
            ))

        return KvkSearchResponse(
            resultaten=resultaten,
            totaal=data.get("totaal", len(resultaten)),
        )

    except httpx.TimeoutException:
        logger.warning("KVK API timeout")
        return KvkSearchResponse(resultaten=[], totaal=0)
    except Exception as e:
        logger.error(f"KVK API error: {e}")
        return KvkSearchResponse(resultaten=[], totaal=0)


@router.get("/valideer-kvk")
async def validate_kvk_number(
    kvk_nummer: str = Query(..., min_length=8, max_length=8, description="KvK-nummer (8 cijfers)"),
):
    """
    Validate a KVK number by looking it up in the Handelsregister.
    Returns company name and address if found.
    """
    if not kvk_nummer.isdigit() or len(kvk_nummer) != 8:
        return {"geldig": False, "melding": "KvK-nummer moet 8 cijfers zijn"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{settings.KVK_API_URL}/zoeken",
                params={"kvkNummer": kvk_nummer},
                headers={"apikey": settings.KVK_API_KEY},
            )

        if response.status_code in (404, 204):
            return {"geldig": False, "melding": "KvK-nummer niet gevonden"}

        if response.status_code != 200:
            return {"geldig": False, "melding": "Kon KvK-nummer niet valideren"}

        data = response.json()
        resultaten = data.get("resultaten", [])

        if not resultaten:
            return {"geldig": False, "melding": "KvK-nummer niet gevonden"}

        item = resultaten[0]
        naam = item.get("naam", "")
        adres_data = item.get("adres", {})
        binnenlands = adres_data.get("binnenlandsAdres", {})
        plaats = binnenlands.get("plaats", "")

        return {
            "geldig": True,
            "naam": naam,
            "plaats": plaats,
            "melding": f"{naam}" + (f" · {plaats}" if plaats else ""),
        }

    except httpx.TimeoutException:
        return {"geldig": False, "melding": "KVK service niet bereikbaar"}
    except Exception as e:
        logger.error(f"KVK validate error: {e}")
        return {"geldig": False, "melding": "Kon KvK-nummer niet valideren"}


@router.get("/valideer-btw")
async def validate_btw_number(
    btw_nummer: str = Query(..., min_length=2, max_length=20, description="EU BTW-nummer"),
):
    """
    Validate an EU VAT number via the VIES API.
    No authentication required (public endpoint).
    """
    # Clean the BTW number
    cleaned = btw_nummer.replace(" ", "").replace(".", "").replace("-", "").upper()

    if len(cleaned) < 4:
        return {"geldig": False, "melding": "BTW-nummer te kort"}

    # Extract country code and number
    country_code = cleaned[:2]
    vat_number = cleaned[2:]

    if not country_code.isalpha():
        return {"geldig": False, "melding": "BTW-nummer moet beginnen met een landcode (bijv. NL)"}

    try:
        # VIES REST API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number",
                params={
                    "countryCode": country_code,
                    "vatNumber": vat_number,
                },
            )

        if response.status_code == 200:
            data = response.json()
            is_valid = data.get("valid", False)
            name = data.get("name", "")
            address = data.get("address", "")

            return {
                "geldig": is_valid,
                "naam": name if name and name != "---" else None,
                "adres": address if address and address != "---" else None,
                "melding": "BTW-nummer is geldig" if is_valid else "BTW-nummer is ongeldig",
            }
        else:
            return {"geldig": False, "melding": "Kon BTW-nummer niet valideren"}

    except httpx.TimeoutException:
        return {"geldig": False, "melding": "VIES service niet bereikbaar"}
    except Exception as e:
        logger.error(f"VIES API error: {e}")
        return {"geldig": False, "melding": "Kon BTW-nummer niet valideren"}
