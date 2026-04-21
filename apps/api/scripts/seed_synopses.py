"""Seed approved synopses for all 10 countries."""

import uuid
from datetime import UTC, datetime

from atlas_api.db import SessionLocal
from atlas_api.models import Synopsis
from sqlalchemy import select

SYNOPSES = {
    "ETH": {
        "text": "Ethiopia faces acute external financing constraints following the Tigray conflict economic disruption and subsequent external debt moratorium. Active debt restructuring under G20 Common Framework with official creditors, post-Pretoria Peace Agreement stabilization. IMF ECF program approved 2023 provides financing anchor. Birr devaluation July 2024 (+30%) a critical macro-structural step, but implementation fragile. Data quality limited — ATLAS applies data uncertainty discount.\n\nThe post-conflict reconstruction phase is straining fiscal resources while revenue mobilization remains below Sub-Saharan African averages. External debt service obligations are unsustainable without restructuring completion. The Birr's managed float is showing signs of parallel market re-emergence, with the premium widening to approximately 15-20% in informal markets.\n\nPositive signals include improving agricultural output post-conflict, early-stage GERD hydropower exports to neighboring countries, and continued multilateral engagement. However, political fragmentation risks remain elevated with regional tensions persisting in Amhara and Oromia regions.",  # noqa: E501
        "key_points": [
            {
                "text": "G20 Common Framework restructuring ongoing — creditor agreement pending",
                "category": "debt",
            },
            {
                "text": "IMF ECF program provides $3.4bn financing anchor over 4 years",
                "category": "imf",
            },
            {"text": "Birr devaluation pass-through driving inflation above 25%", "category": "fx"},
            {"text": "Post-conflict reconstruction creating fiscal pressure", "category": "fiscal"},
        ],
    },
    "GHA": {
        "text": "Ghana completed its domestic debt exchange program in 2023 and is progressing through external debt restructuring under the G20 Common Framework. The IMF ECF program provides a credibility anchor, with fiscal consolidation targets being met through revenue mobilization and expenditure controls.\n\nThe Cedi has stabilized following the 2022 crisis but remains under depreciation pressure. Cocoa and gold exports provide the primary hard currency buffer, though cocoa production faces climate-related headwinds. The banking sector absorbed significant losses from the domestic debt exchange but has been recapitalized.\n\nGrowth is recovering from the 2022 crisis trough, with the IMF projecting gradual improvement toward 4% by 2026. However, debt sustainability remains fragile and highly sensitive to commodity price assumptions.",  # noqa: E501
        "key_points": [
            {
                "text": "Domestic debt exchange completed — external restructuring progressing",
                "category": "debt",
            },
            {"text": "IMF ECF program on track with fiscal targets met", "category": "imf"},
            {
                "text": "Banking sector recapitalized post-debt exchange losses",
                "category": "financial",
            },
        ],
    },
    "KEN": {
        "text": "Kenya faces elevated external debt service pressure with significant Eurobond maturities concentrated in 2024-2027. The IMF EFF program provides a policy framework anchor, with Kenya maintaining relatively strong institutional credibility compared to regional peers.\n\nThe Shilling has depreciated significantly against the USD but CBK reserves remain adequate at approximately 4 months of import cover. Revenue mobilization through the Finance Act 2023 generated political backlash but improved fiscal metrics. The diversified economy (agriculture, services, technology) provides resilience against single-commodity shocks.\n\nPolitical risk is moderate with the 2027 election cycle approaching. Kenya's position as the EAC regional hub and tech sector growth (fintech, mobile payments) provide structural growth support.",  # noqa: E501
        "key_points": [
            {
                "text": "Eurobond maturity wall 2024-2027 is primary external risk",
                "category": "debt",
            },
            {"text": "IMF EFF program provides policy anchor", "category": "imf"},
            {
                "text": "Diversified economy reduces commodity concentration risk",
                "category": "growth",
            },
            {"text": "CBK reserves adequate at ~4 months import cover", "category": "reserves"},
        ],
    },
    "NGA": {
        "text": "Nigeria is undergoing significant macroeconomic reform following the FX unification announced in mid-2023. The Naira has depreciated substantially but the parallel market premium has narrowed significantly, improving investor confidence and FDI prospects.\n\nThe removal of the fuel subsidy combined with Naira depreciation has driven inflation above 30%, creating social pressure. However, fiscal space has improved materially — the subsidy removal alone saves approximately 2% of GDP annually. The Dangote refinery coming online is expected to reduce the fuel import bill structurally.\n\nOil production remains below OPEC quota at approximately 1.4mbpd vs. 1.8mbpd quota, limiting the FX benefit of reform. Non-oil revenue mobilization and the Tinubu administration's reform momentum are the key variables for the medium-term trajectory.",  # noqa: E501
        "key_points": [
            {"text": "FX unification narrowing parallel market premium", "category": "fx"},
            {"text": "Fuel subsidy removal saving ~2% GDP annually", "category": "fiscal"},
            {"text": "Oil production below OPEC quota limiting FX inflows", "category": "external"},
            {
                "text": "Dangote refinery to structurally reduce fuel import bill",
                "category": "growth",
            },
        ],
    },
    "CIV": {
        "text": "Côte d'Ivoire maintains its position as the strongest performer in the WAEMU zone with GDP growth consistently above 6%. The CFA franc peg to the Euro provides FX stability, though it limits monetary policy flexibility in response to country-specific shocks.\n\nThe cocoa sector remains the dominant export earner, creating concentration risk particularly as climate change threatens West African cocoa production. Fiscal management has been prudent with debt-to-GDP ratios below WAEMU convergence criteria, though infrastructure investment spending is rising.\n\nPolitical succession risk is the primary concern as the post-Ouattara transition approaches. The 2025 political cycle will test institutional resilience. However, Abidjan's emergence as a regional financial hub and continued infrastructure development provide structural growth momentum.",  # noqa: E501
        "key_points": [
            {"text": "Strongest WAEMU performer with 6%+ GDP growth", "category": "growth"},
            {
                "text": "CFA peg provides FX stability but limits monetary flexibility",
                "category": "fx",
            },
            {
                "text": "Cocoa concentration creates climate-related commodity risk",
                "category": "external",
            },
        ],
    },
    "SEN": {
        "text": "Senegal is at an inflection point with the Sangomar oil field and Greater Tortue Ahmeyim (GTA) gas project coming online, potentially transforming the country's external balance and fiscal position. However, recent fiscal data revisions have raised credibility concerns with rating agencies.\n\nThe WAEMU membership provides monetary stability through the CFA franc peg. Remittances from the diaspora remain a critical source of external financing. The new political leadership following the 2024 election has signaled continuity on economic policy while pursuing anti-corruption measures.\n\nDebt levels have risen significantly due to infrastructure spending, and the revised fiscal data suggests the fiscal deficit was larger than previously reported. The hydrocarbon revenue timeline and management framework will be critical for medium-term sustainability.",  # noqa: E501
        "key_points": [
            {
                "text": "Sangomar oil and GTA gas production transformative for external balance",
                "category": "external",
            },
            {"text": "Fiscal data revisions raised credibility concerns", "category": "fiscal"},
            {
                "text": "New political leadership signaling policy continuity",
                "category": "political",
            },
        ],
    },
    "RWA": {
        "text": "Rwanda maintains strong governance and business environment rankings, consistently outperforming regional peers on institutional quality metrics. The economy has diversified from agriculture toward services and technology, with Kigali positioning as an ICT and conference hub.\n\nThe small open economy is vulnerable to external shocks and terms-of-trade deterioration. Limited fiscal space constrains countercyclical policy options. The concentration of political power, while providing policy consistency, raises long-term governance perception risk among some international investors.\n\nGrowth prospects remain robust, supported by the Made in Rwanda import substitution strategy and regional trade integration through the EAC. Tourism continues to recover post-pandemic with high-end ecotourism driving revenue growth.",  # noqa: E501
        "key_points": [
            {
                "text": "Strong governance rankings support investor confidence",
                "category": "political",
            },
            {"text": "Small open economy vulnerable to external shocks", "category": "external"},
            {
                "text": "Technology-led growth strategy diversifying from agriculture",
                "category": "growth",
            },
        ],
    },
    "ZAF": {
        "text": "South Africa faces structural growth constraints from the ongoing energy crisis (load-shedding), record unemployment above 30%, and state-owned enterprise (SOE) contingent liabilities. The Government of National Unity (GNU) coalition formed after the 2024 election has provided a policy stability signal that improved market sentiment.\n\nThe deep and liquid capital markets remain a structural advantage, with the Johannesburg Stock Exchange and bond market providing financing access that most African sovereigns lack. The Rand floats freely with deep FX market liquidity.\n\nThe renewable energy transition is creating a significant investment wave through the REIPP program. Eskom's debt restructuring and operational unbundling are progressing but remain the single largest fiscal risk. AGOA trade preferences with the US provide export market access but are subject to periodic review.",  # noqa: E501
        "key_points": [
            {"text": "Load-shedding energy crisis constraining GDP growth", "category": "growth"},
            {"text": "GNU coalition providing policy stability signal", "category": "political"},
            {
                "text": "Deep capital markets a structural financing advantage",
                "category": "financial",
            },
            {
                "text": "Eskom SOE contingent liabilities are primary fiscal risk",
                "category": "fiscal",
            },
        ],
    },
    "MAR": {
        "text": "Morocco maintains investment-grade adjacent credit quality with strong institutional frameworks and a diversified economy. The basket peg (60% EUR / 40% USD with ±5% band) provides exchange rate stability while allowing limited flexibility.\n\nThe 2023 earthquake reconstruction has added fiscal pressure but the response has demonstrated institutional capacity. Water stress and agricultural drought risk are structural concerns that affect rural GDP and food inflation. The EU remains the dominant trade partner, creating concentration risk.\n\nThe automotive and aerospace manufacturing sectors have grown significantly, positioning Morocco as a nearshoring hub for European supply chains. The 2030 FIFA World Cup co-hosting (with Spain and Portugal) will drive infrastructure investment over the coming years. Renewable energy leadership through the Noor solar complex positions Morocco well for the energy transition.",  # noqa: E501
        "key_points": [
            {"text": "Investment-grade adjacent with strong institutions", "category": "rating"},
            {"text": "Manufacturing hub for European nearshoring", "category": "growth"},
            {"text": "2030 FIFA World Cup driving infrastructure investment", "category": "fiscal"},
            {"text": "Water stress and drought are structural risks", "category": "external"},
        ],
    },
    "EGY": {
        "text": "Egypt is navigating a post-devaluation stabilization phase supported by the IMF EFF program and the landmark Ras El-Hekma deal which brought $35bn in investment commitments. The EGP devaluation (~60% in March 2024) has narrowed the parallel market gap significantly, restoring investor confidence.\n\nInflation remains elevated above 25% as the devaluation pass-through works through the economy, though the trajectory is improving. Suez Canal revenues have been disrupted by Red Sea shipping route changes, removing a critical hard currency source. Tourism recovery post-pandemic has been positive but remains sensitive to regional geopolitical developments.\n\nMega-project spending (new administrative capital, infrastructure) continues to strain the fiscal position. External financing needs remain large, and the debt-to-GDP ratio has risen significantly. Gas exports provide some hard currency buffer but production has plateaued. The IMF program conditions on structural reforms (privatization, competition policy) are the key test of reform commitment.",  # noqa: E501
        "key_points": [
            {"text": "Ras El-Hekma deal providing $35bn investment anchor", "category": "external"},
            {"text": "Post-devaluation parallel market gap narrowed", "category": "fx"},
            {"text": "Suez Canal revenue disrupted by Red Sea rerouting", "category": "external"},
            {"text": "IMF EFF program conditions testing reform commitment", "category": "imf"},
        ],
    },
}


def main() -> None:
    now = datetime.now(UTC)
    with SessionLocal() as s:
        for iso3, data in SYNOPSES.items():
            existing = (
                s.execute(
                    select(Synopsis).where(
                        Synopsis.iso3 == iso3,
                        Synopsis.approval_state.in_(
                            [
                                "human_approved",
                                "auto_approved_similarity",
                                "auto_approved_stable_country",
                            ]
                        ),
                    )
                )
                .scalars()
                .first()
            )
            if existing:
                print(f"{iso3}: already has approved synopsis, skipping")
                continue

            synopsis = Synopsis(
                id=uuid.uuid4(),
                iso3=iso3,
                text=data["text"],
                key_points=data["key_points"],
                generated_at=now,
                approval_state="human_approved",
                approved_at=now,
            )
            s.add(synopsis)
            print(f"{iso3}: seeded synopsis")
        s.commit()


if __name__ == "__main__":
    main()
