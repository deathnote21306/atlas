"""Internal MacroIndicator ↔ external source code mapping."""

from atlas_schemas.macro import MacroIndicator

WORLDBANK_CODES: dict[MacroIndicator, str] = {
    MacroIndicator.GDP_USD: "NY.GDP.MKTP.CD",
    MacroIndicator.GDP_GROWTH_PCT: "NY.GDP.MKTP.KD.ZG",
    MacroIndicator.INFLATION_PCT: "FP.CPI.TOTL.ZG",
    MacroIndicator.CURRENT_ACCOUNT_PCT_GDP: "BN.CAB.XOKA.GD.ZS",
    MacroIndicator.FISCAL_BALANCE_PCT_GDP: "GC.BAL.CASH.GD.ZS",
    MacroIndicator.PUBLIC_DEBT_PCT_GDP: "GC.DOD.TOTL.GD.ZS",
    MacroIndicator.EXTERNAL_DEBT_PCT_GNI: "DT.DOD.DECT.GN.ZS",
    MacroIndicator.FX_RESERVES_MO_IMPORTS: "FI.RES.TOTL.MO",
    MacroIndicator.DEBT_SERVICE_PCT_EXPORTS: "DT.TDS.DECT.EX.ZS",
    MacroIndicator.UNEMPLOYMENT_PCT: "SL.UEM.TOTL.ZS",
    MacroIndicator.FDI_INFLOW_USD: "BX.KLT.DINV.CD.WD",
    MacroIndicator.GDP_PER_CAPITA_USD: "NY.GDP.PCAP.CD",
}

IMF_WEO_CODES: dict[MacroIndicator, str] = {
    MacroIndicator.GDP_USD: "NGDPD",
    MacroIndicator.GDP_GROWTH_PCT: "NGDP_RPCH",
    MacroIndicator.INFLATION_PCT: "PCPIPCH",
    MacroIndicator.CURRENT_ACCOUNT_PCT_GDP: "BCA_NGDPD",
    MacroIndicator.FISCAL_BALANCE_PCT_GDP: "GGXCNL_NGDP",
    MacroIndicator.PUBLIC_DEBT_PCT_GDP: "GGXWDG_NGDP",
    MacroIndicator.UNEMPLOYMENT_PCT: "LUR",
    MacroIndicator.GDP_PER_CAPITA_USD: "NGDPDPC",
}

ISO3_TO_CCY: dict[str, str] = {
    "CIV": "XOF", "GHA": "GHS", "KEN": "KES", "NGA": "NGN", "SEN": "XOF",
    "ETH": "ETB", "RWA": "RWF", "ZAF": "ZAR", "MAR": "MAD", "EGY": "EGP",
}
