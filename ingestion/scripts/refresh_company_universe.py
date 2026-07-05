"""Refresh reusable company universe seeds and progress tracking.

This script is intentionally conservative:
- It appends missing companies/products/sources/relationships only.
- New relationship rows are status=candidate.
- It uses SEC official JSON endpoints for US company metadata and latest filings.

Usage:
    python ingestion/scripts/refresh_company_universe.py --write
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SEEDS = ROOT / "ingestion" / "seeds"
PROGRESS = ROOT / "ingestion" / "progress"

USER_AGENT = "IndustryNetworkMap/0.1 contact: local-research@example.com"
TODAY = date.today().isoformat()

US_UNIVERSE = [
    {
        "rank": 1,
        "ticker": "MSFT",
        "company_id": "US_MSFT",
        "name": "Microsoft",
        "english_name": "Microsoft Corporation",
        "exchange": "NASDAQ",
        "website": "https://www.microsoft.com",
        "aliases": "Microsoft;Azure;MSFT",
        "description": "大型 cloud、AI、enterprise software 公司，Azure 是主要 data center 與 AI 基礎設施平台。",
        "products": ["cloud_infrastructure_service", "enterprise_software"],
    },
    {
        "rank": 2,
        "ticker": "GOOGL",
        "company_id": "US_GOOGL",
        "name": "Alphabet",
        "english_name": "Alphabet Inc.",
        "exchange": "NASDAQ",
        "website": "https://abc.xyz",
        "aliases": "Google;Alphabet;Google Cloud;GOOGL",
        "description": "Google 母公司，核心包含 search、online advertising、Google Cloud 與 AI 基礎設施。",
        "products": ["search_engine_service", "online_advertising_service", "cloud_infrastructure_service"],
    },
    {
        "rank": 3,
        "ticker": "AMZN",
        "company_id": "US_AMZN",
        "name": "Amazon",
        "english_name": "Amazon.com, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.amazon.com",
        "aliases": "Amazon;AWS;AMZN",
        "description": "大型 ecommerce 與 cloud 公司，AWS 是全球主要 cloud infrastructure 與 AI data center 平台。",
        "products": ["ecommerce_marketplace", "cloud_infrastructure_service"],
    },
    {
        "rank": 4,
        "ticker": "META",
        "company_id": "US_META",
        "name": "Meta",
        "english_name": "Meta Platforms, Inc.",
        "exchange": "NASDAQ",
        "website": "https://about.meta.com",
        "aliases": "Facebook;Instagram;WhatsApp;META",
        "description": "大型 social media 與 online advertising 平台，並大量投資 AI infrastructure。",
        "products": ["social_media_platform", "online_advertising_service"],
    },
    {
        "rank": 5,
        "ticker": "TSLA",
        "company_id": "US_TSLA",
        "name": "Tesla",
        "english_name": "Tesla, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.tesla.com",
        "aliases": "Tesla;TSLA",
        "description": "大型 electric vehicle、energy storage 與 autonomous driving 平台公司。",
        "products": ["electric_vehicle", "energy_storage_system", "autonomous_driving_platform"],
    },
    {
        "rank": 6,
        "ticker": "AVGO",
        "company_id": "US_AVGO",
        "name": "Broadcom",
        "english_name": "Broadcom Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.broadcom.com",
        "aliases": "Broadcom;AVGO",
        "description": "大型 semiconductor 與 infrastructure software 公司，產品涵蓋 network IC、custom AI accelerator 與 connectivity。",
        "products": ["network_ic", "custom_ai_accelerator", "enterprise_software"],
    },
    {
        "rank": 7,
        "ticker": "ORCL",
        "company_id": "US_ORCL",
        "name": "Oracle",
        "english_name": "Oracle Corporation",
        "exchange": "NYSE",
        "website": "https://www.oracle.com",
        "aliases": "Oracle;OCI;ORCL",
        "description": "大型 database software、enterprise software 與 cloud infrastructure 公司。",
        "products": ["database_software", "enterprise_software", "cloud_infrastructure_service"],
    },
    {
        "rank": 8,
        "ticker": "CRM",
        "company_id": "US_CRM",
        "name": "Salesforce",
        "english_name": "Salesforce, Inc.",
        "exchange": "NYSE",
        "website": "https://www.salesforce.com",
        "aliases": "Salesforce;CRM",
        "description": "大型 SaaS 與 enterprise software 公司，核心為 CRM 與企業雲端應用。",
        "products": ["enterprise_software"],
    },
    {
        "rank": 9,
        "ticker": "NFLX",
        "company_id": "US_NFLX",
        "name": "Netflix",
        "english_name": "Netflix, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.netflix.com",
        "aliases": "Netflix;NFLX",
        "description": "大型 streaming service 與內容平台公司。",
        "products": ["streaming_service"],
    },
    {
        "rank": 10,
        "ticker": "ADBE",
        "company_id": "US_ADBE",
        "name": "Adobe",
        "english_name": "Adobe Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.adobe.com",
        "aliases": "Adobe;Creative Cloud;ADBE",
        "description": "大型 creative software、document cloud 與 digital experience software 公司。",
        "products": ["creative_software", "enterprise_software"],
    },
    {
        "rank": 11,
        "ticker": "QCOM",
        "company_id": "US_QCOM",
        "name": "Qualcomm",
        "english_name": "QUALCOMM Incorporated",
        "exchange": "NASDAQ",
        "website": "https://www.qualcomm.com",
        "aliases": "Qualcomm;Snapdragon;QCOM",
        "description": "大型 mobile SoC、wireless modem 與 connectivity IC 設計公司。",
        "products": ["smartphone_soc", "network_ic"],
    },
    {
        "rank": 12,
        "ticker": "INTC",
        "company_id": "US_INTC",
        "name": "Intel",
        "english_name": "Intel Corporation",
        "exchange": "NASDAQ",
        "website": "https://www.intel.com",
        "aliases": "Intel;INTC",
        "description": "大型 CPU、data center、semiconductor manufacturing 與 foundry 公司。",
        "products": ["server_cpu", "wafer_foundry_service"],
    },
    {
        "rank": 13,
        "ticker": "IBM",
        "company_id": "US_IBM",
        "name": "IBM",
        "english_name": "International Business Machines Corporation",
        "exchange": "NYSE",
        "website": "https://www.ibm.com",
        "aliases": "IBM;Red Hat",
        "description": "大型 hybrid cloud、AI、enterprise software 與 IT service 公司。",
        "products": ["enterprise_software", "cloud_infrastructure_service"],
    },
    {
        "rank": 14,
        "ticker": "CSCO",
        "company_id": "US_CSCO",
        "name": "Cisco",
        "english_name": "Cisco Systems, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.cisco.com",
        "aliases": "Cisco;CSCO",
        "description": "大型 networking equipment、switch、router 與 security 產品公司。",
        "products": ["networking_switch", "cybersecurity_software"],
    },
    {
        "rank": 15,
        "ticker": "TXN",
        "company_id": "US_TXN",
        "name": "Texas Instruments",
        "english_name": "Texas Instruments Incorporated",
        "exchange": "NASDAQ",
        "website": "https://www.ti.com",
        "aliases": "Texas Instruments;TI;TXN",
        "description": "大型 analog IC 與 embedded processor 半導體公司。",
        "products": ["analog_ic"],
    },
    {
        "rank": 16,
        "ticker": "AMAT",
        "company_id": "US_AMAT",
        "name": "Applied Materials",
        "english_name": "Applied Materials, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.appliedmaterials.com",
        "aliases": "Applied Materials;AMAT",
        "description": "大型 semiconductor equipment 公司，供應晶圓製程設備與服務。",
        "products": ["semiconductor_equipment_product"],
    },
    {
        "rank": 17,
        "ticker": "LRCX",
        "company_id": "US_LRCX",
        "name": "Lam Research",
        "english_name": "Lam Research Corporation",
        "exchange": "NASDAQ",
        "website": "https://www.lamresearch.com",
        "aliases": "Lam Research;LRCX",
        "description": "大型 wafer fabrication equipment 公司，產品用於 semiconductor 製程。",
        "products": ["semiconductor_equipment_product"],
    },
    {
        "rank": 18,
        "ticker": "NOW",
        "company_id": "US_NOW",
        "name": "ServiceNow",
        "english_name": "ServiceNow, Inc.",
        "exchange": "NYSE",
        "website": "https://www.servicenow.com",
        "aliases": "ServiceNow;NOW",
        "description": "大型 enterprise workflow automation 與 SaaS 平台公司。",
        "products": ["enterprise_software"],
    },
    {
        "rank": 19,
        "ticker": "PANW",
        "company_id": "US_PANW",
        "name": "Palo Alto Networks",
        "english_name": "Palo Alto Networks, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.paloaltonetworks.com",
        "aliases": "Palo Alto Networks;PANW",
        "description": "大型 cybersecurity software 與 network security 平台公司。",
        "products": ["cybersecurity_software"],
    },
    {
        "rank": 20,
        "ticker": "UBER",
        "company_id": "US_UBER",
        "name": "Uber",
        "english_name": "Uber Technologies, Inc.",
        "exchange": "NYSE",
        "website": "https://www.uber.com",
        "aliases": "Uber;UBER",
        "description": "大型 mobility platform、delivery platform 與 marketplace 公司。",
        "products": ["mobility_platform"],
    },
    {
        "rank": 21,
        "ticker": "JPM",
        "company_id": "US_JPM",
        "name": "JPMorgan Chase",
        "english_name": "JPMorgan Chase & Co.",
        "exchange": "NYSE",
        "website": "https://www.jpmorganchase.com",
        "aliases": "JPMorgan Chase;JPM",
        "description": "大型 banking、investment banking 與 financial service 公司。",
        "products": ["financial_service"],
    },
    {
        "rank": 22,
        "ticker": "V",
        "company_id": "US_V",
        "name": "Visa",
        "english_name": "Visa Inc.",
        "exchange": "NYSE",
        "website": "https://www.visa.com",
        "aliases": "Visa;V",
        "description": "大型 payment network 與 digital payment infrastructure 公司。",
        "products": ["payment_network"],
    },
    {
        "rank": 23,
        "ticker": "MA",
        "company_id": "US_MA",
        "name": "Mastercard",
        "english_name": "Mastercard Incorporated",
        "exchange": "NYSE",
        "website": "https://www.mastercard.com",
        "aliases": "Mastercard;MA",
        "description": "大型 payment network 與 digital payment infrastructure 公司。",
        "products": ["payment_network"],
    },
    {
        "rank": 24,
        "ticker": "WMT",
        "company_id": "US_WMT",
        "name": "Walmart",
        "english_name": "Walmart Inc.",
        "exchange": "NYSE",
        "website": "https://www.walmart.com",
        "aliases": "Walmart;WMT",
        "description": "大型 retail、grocery 與 ecommerce 公司。",
        "products": ["retail_service", "ecommerce_marketplace"],
    },
]

ADDITIONAL_US_UNIVERSE = [
    {
        "rank": 25,
        "ticker": "LLY",
        "company_id": "US_LLY",
        "name": "Eli Lilly",
        "english_name": "Eli Lilly and Company",
        "exchange": "NYSE",
        "website": "https://www.lilly.com",
        "aliases": "Eli Lilly;Lilly;LLY",
        "description": "Large US pharmaceutical company focused on diabetes, obesity, oncology, immunology, and neuroscience medicines.",
        "products": ["pharmaceutical_product"],
    },
    {
        "rank": 26,
        "ticker": "UNH",
        "company_id": "US_UNH",
        "name": "UnitedHealth Group",
        "english_name": "UnitedHealth Group Incorporated",
        "exchange": "NYSE",
        "website": "https://www.unitedhealthgroup.com",
        "aliases": "UnitedHealth;Optum;UNH",
        "description": "Large US healthcare and health insurance company with Optum health services and data operations.",
        "products": ["healthcare_service", "health_insurance_service"],
    },
    {
        "rank": 27,
        "ticker": "JNJ",
        "company_id": "US_JNJ",
        "name": "Johnson & Johnson",
        "english_name": "Johnson & Johnson",
        "exchange": "NYSE",
        "website": "https://www.jnj.com",
        "aliases": "Johnson & Johnson;J&J;JNJ",
        "description": "Large US healthcare company focused on innovative medicine and medtech.",
        "products": ["pharmaceutical_product", "medical_device"],
    },
    {
        "rank": 28,
        "ticker": "ABBV",
        "company_id": "US_ABBV",
        "name": "AbbVie",
        "english_name": "AbbVie Inc.",
        "exchange": "NYSE",
        "website": "https://www.abbvie.com",
        "aliases": "AbbVie;ABBV",
        "description": "Large US biopharmaceutical company focused on immunology, oncology, neuroscience, and aesthetics.",
        "products": ["pharmaceutical_product"],
    },
    {
        "rank": 29,
        "ticker": "MRK",
        "company_id": "US_MRK",
        "name": "Merck",
        "english_name": "Merck & Co., Inc.",
        "exchange": "NYSE",
        "website": "https://www.merck.com",
        "aliases": "Merck;MSD;MRK",
        "description": "Large US pharmaceutical company focused on oncology, vaccines, hospital acute care, and animal health.",
        "products": ["pharmaceutical_product"],
    },
    {
        "rank": 30,
        "ticker": "ABT",
        "company_id": "US_ABT",
        "name": "Abbott",
        "english_name": "Abbott Laboratories",
        "exchange": "NYSE",
        "website": "https://www.abbott.com",
        "aliases": "Abbott;ABT",
        "description": "Large US healthcare company focused on diagnostics, medical devices, nutrition, and medicines.",
        "products": ["medical_device", "diagnostics_instrument"],
    },
    {
        "rank": 31,
        "ticker": "TMO",
        "company_id": "US_TMO",
        "name": "Thermo Fisher Scientific",
        "english_name": "Thermo Fisher Scientific Inc.",
        "exchange": "NYSE",
        "website": "https://www.thermofisher.com",
        "aliases": "Thermo Fisher;TMO",
        "description": "Large US life science tools company providing analytical instruments, reagents, consumables, and services.",
        "products": ["diagnostics_instrument", "life_science_tool"],
    },
    {
        "rank": 32,
        "ticker": "ISRG",
        "company_id": "US_ISRG",
        "name": "Intuitive Surgical",
        "english_name": "Intuitive Surgical, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.intuitive.com",
        "aliases": "Intuitive Surgical;da Vinci;ISRG",
        "description": "Large US medical device company focused on robotic-assisted surgical systems.",
        "products": ["medical_device", "surgical_robot"],
    },
    {
        "rank": 33,
        "ticker": "XOM",
        "company_id": "US_XOM",
        "name": "Exxon Mobil",
        "english_name": "Exxon Mobil Corporation",
        "exchange": "NYSE",
        "website": "https://corporate.exxonmobil.com",
        "aliases": "ExxonMobil;XOM",
        "description": "Large US integrated energy company producing oil, natural gas, fuels, chemicals, and low-carbon solutions.",
        "products": ["oil_gas_product", "petrochemical_product"],
    },
    {
        "rank": 34,
        "ticker": "CVX",
        "company_id": "US_CVX",
        "name": "Chevron",
        "english_name": "Chevron Corporation",
        "exchange": "NYSE",
        "website": "https://www.chevron.com",
        "aliases": "Chevron;CVX",
        "description": "Large US integrated energy company producing oil, natural gas, fuels, lubricants, and chemicals.",
        "products": ["oil_gas_product", "refined_petroleum"],
    },
    {
        "rank": 35,
        "ticker": "COP",
        "company_id": "US_COP",
        "name": "ConocoPhillips",
        "english_name": "ConocoPhillips",
        "exchange": "NYSE",
        "website": "https://www.conocophillips.com",
        "aliases": "ConocoPhillips;COP",
        "description": "Large US exploration and production company focused on oil and natural gas.",
        "products": ["oil_gas_product"],
    },
    {
        "rank": 36,
        "ticker": "SLB",
        "company_id": "US_SLB",
        "name": "SLB",
        "english_name": "Schlumberger Limited",
        "exchange": "NYSE",
        "website": "https://www.slb.com",
        "aliases": "Schlumberger;SLB",
        "description": "Large oilfield services company providing drilling, reservoir, production, and digital energy technology.",
        "products": ["oilfield_service", "industrial_software"],
    },
    {
        "rank": 37,
        "ticker": "COST",
        "company_id": "US_COST",
        "name": "Costco",
        "english_name": "Costco Wholesale Corporation",
        "exchange": "NASDAQ",
        "website": "https://www.costco.com",
        "aliases": "Costco;COST",
        "description": "Large membership warehouse retailer selling consumer goods, grocery, fuel, and ecommerce services.",
        "products": ["retail_service", "ecommerce_marketplace"],
    },
    {
        "rank": 38,
        "ticker": "HD",
        "company_id": "US_HD",
        "name": "Home Depot",
        "english_name": "The Home Depot, Inc.",
        "exchange": "NYSE",
        "website": "https://www.homedepot.com",
        "aliases": "Home Depot;HD",
        "description": "Large home improvement retailer serving professional contractors and consumers.",
        "products": ["home_improvement_retail", "retail_service"],
    },
    {
        "rank": 39,
        "ticker": "MCD",
        "company_id": "US_MCD",
        "name": "McDonald's",
        "english_name": "McDonald's Corporation",
        "exchange": "NYSE",
        "website": "https://www.mcdonalds.com",
        "aliases": "McDonald's;MCD",
        "description": "Large global restaurant brand and franchising company.",
        "products": ["restaurant_service"],
    },
    {
        "rank": 40,
        "ticker": "SBUX",
        "company_id": "US_SBUX",
        "name": "Starbucks",
        "english_name": "Starbucks Corporation",
        "exchange": "NASDAQ",
        "website": "https://www.starbucks.com",
        "aliases": "Starbucks;SBUX",
        "description": "Large coffee retail and restaurant company with company-operated and licensed stores.",
        "products": ["restaurant_service", "beverage_product"],
    },
    {
        "rank": 41,
        "ticker": "KO",
        "company_id": "US_KO",
        "name": "Coca-Cola",
        "english_name": "The Coca-Cola Company",
        "exchange": "NYSE",
        "website": "https://www.coca-colacompany.com",
        "aliases": "Coca-Cola;KO",
        "description": "Large beverage company with global concentrate, syrup, and finished beverage brands.",
        "products": ["beverage_product"],
    },
    {
        "rank": 42,
        "ticker": "PEP",
        "company_id": "US_PEP",
        "name": "PepsiCo",
        "english_name": "PepsiCo, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.pepsico.com",
        "aliases": "PepsiCo;Pepsi;PEP",
        "description": "Large beverage and convenient foods company with global brands.",
        "products": ["beverage_product", "food_beverage_product"],
    },
    {
        "rank": 43,
        "ticker": "PG",
        "company_id": "US_PG",
        "name": "Procter & Gamble",
        "english_name": "The Procter & Gamble Company",
        "exchange": "NYSE",
        "website": "https://www.pg.com",
        "aliases": "P&G;Procter & Gamble;PG",
        "description": "Large consumer goods company focused on beauty, grooming, health care, fabric care, home care, and baby care.",
        "products": ["consumer_goods"],
    },
    {
        "rank": 44,
        "ticker": "BAC",
        "company_id": "US_BAC",
        "name": "Bank of America",
        "english_name": "Bank of America Corporation",
        "exchange": "NYSE",
        "website": "https://www.bankofamerica.com",
        "aliases": "Bank of America;BofA;BAC",
        "description": "Large US bank providing consumer banking, wealth management, investment banking, and markets services.",
        "products": ["financial_service"],
    },
    {
        "rank": 45,
        "ticker": "WFC",
        "company_id": "US_WFC",
        "name": "Wells Fargo",
        "english_name": "Wells Fargo & Company",
        "exchange": "NYSE",
        "website": "https://www.wellsfargo.com",
        "aliases": "Wells Fargo;WFC",
        "description": "Large US bank providing consumer, commercial, corporate, and investment banking services.",
        "products": ["financial_service"],
    },
    {
        "rank": 46,
        "ticker": "GS",
        "company_id": "US_GS",
        "name": "Goldman Sachs",
        "english_name": "The Goldman Sachs Group, Inc.",
        "exchange": "NYSE",
        "website": "https://www.goldmansachs.com",
        "aliases": "Goldman Sachs;GS",
        "description": "Large global investment bank and asset management company.",
        "products": ["financial_service", "securities_service"],
    },
    {
        "rank": 47,
        "ticker": "MS",
        "company_id": "US_MS",
        "name": "Morgan Stanley",
        "english_name": "Morgan Stanley",
        "exchange": "NYSE",
        "website": "https://www.morganstanley.com",
        "aliases": "Morgan Stanley;MS",
        "description": "Large global financial services company focused on wealth management, investment banking, and markets.",
        "products": ["financial_service", "securities_service"],
    },
    {
        "rank": 48,
        "ticker": "BLK",
        "company_id": "US_BLK",
        "name": "BlackRock",
        "english_name": "BlackRock, Inc.",
        "exchange": "NYSE",
        "website": "https://www.blackrock.com",
        "aliases": "BlackRock;BLK",
        "description": "Large asset manager providing investment management, ETFs, advisory, and technology services.",
        "products": ["financial_service", "enterprise_software"],
    },
    {
        "rank": 49,
        "ticker": "SPGI",
        "company_id": "US_SPGI",
        "name": "S&P Global",
        "english_name": "S&P Global Inc.",
        "exchange": "NYSE",
        "website": "https://www.spglobal.com",
        "aliases": "S&P Global;SPGI",
        "description": "Large financial information, ratings, benchmarks, and data analytics company.",
        "products": ["financial_service", "data_analytics_software"],
    },
    {
        "rank": 50,
        "ticker": "GE",
        "company_id": "US_GE",
        "name": "GE Aerospace",
        "english_name": "GE Aerospace",
        "exchange": "NYSE",
        "website": "https://www.geaerospace.com",
        "aliases": "GE Aerospace;General Electric;GE",
        "description": "Large aerospace company producing commercial and defense aircraft engines and systems.",
        "products": ["aerospace_component", "aerospace_defense_system"],
    },
    {
        "rank": 51,
        "ticker": "CAT",
        "company_id": "US_CAT",
        "name": "Caterpillar",
        "english_name": "Caterpillar Inc.",
        "exchange": "NYSE",
        "website": "https://www.caterpillar.com",
        "aliases": "Caterpillar;CAT",
        "description": "Large industrial company producing construction and mining equipment, engines, turbines, and locomotives.",
        "products": ["construction_mining_equipment", "industrial_equipment_product"],
    },
    {
        "rank": 52,
        "ticker": "RTX",
        "company_id": "US_RTX",
        "name": "RTX",
        "english_name": "RTX Corporation",
        "exchange": "NYSE",
        "website": "https://www.rtx.com",
        "aliases": "RTX;Raytheon;Pratt & Whitney;Collins Aerospace",
        "description": "Large aerospace and defense company producing engines, avionics, missiles, sensors, and defense systems.",
        "products": ["aerospace_component", "aerospace_defense_system"],
    },
    {
        "rank": 53,
        "ticker": "HON",
        "company_id": "US_HON",
        "name": "Honeywell",
        "english_name": "Honeywell International Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.honeywell.com",
        "aliases": "Honeywell;HON",
        "description": "Large industrial technology company focused on aerospace, building automation, industrial automation, and energy solutions.",
        "products": ["industrial_automation_equipment", "aerospace_component", "enterprise_software"],
    },
    {
        "rank": 54,
        "ticker": "DE",
        "company_id": "US_DE",
        "name": "Deere",
        "english_name": "Deere & Company",
        "exchange": "NYSE",
        "website": "https://www.deere.com",
        "aliases": "John Deere;Deere;DE",
        "description": "Large agricultural and construction equipment company with precision agriculture technology.",
        "products": ["agricultural_equipment", "construction_mining_equipment"],
    },
    {
        "rank": 55,
        "ticker": "UPS",
        "company_id": "US_UPS",
        "name": "UPS",
        "english_name": "United Parcel Service, Inc.",
        "exchange": "NYSE",
        "website": "https://www.ups.com",
        "aliases": "UPS;United Parcel Service",
        "description": "Large package delivery and logistics company.",
        "products": ["logistics_service"],
    },
    {
        "rank": 56,
        "ticker": "UNP",
        "company_id": "US_UNP",
        "name": "Union Pacific",
        "english_name": "Union Pacific Corporation",
        "exchange": "NYSE",
        "website": "https://www.up.com",
        "aliases": "Union Pacific;UNP",
        "description": "Large US freight railroad company.",
        "products": ["railroad_service", "logistics_service"],
    },
    {
        "rank": 57,
        "ticker": "KLAC",
        "company_id": "US_KLAC",
        "name": "KLA",
        "english_name": "KLA Corporation",
        "exchange": "NASDAQ",
        "website": "https://www.kla.com",
        "aliases": "KLA;KLAC",
        "description": "Large semiconductor process control and yield management equipment company.",
        "products": ["semiconductor_equipment_product"],
    },
    {
        "rank": 58,
        "ticker": "ADI",
        "company_id": "US_ADI",
        "name": "Analog Devices",
        "english_name": "Analog Devices, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.analog.com",
        "aliases": "Analog Devices;ADI",
        "description": "Large analog, mixed-signal, power management, and sensor IC company.",
        "products": ["analog_ic", "power_management_ic"],
    },
    {
        "rank": 59,
        "ticker": "MRVL",
        "company_id": "US_MRVL",
        "name": "Marvell Technology",
        "english_name": "Marvell Technology, Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.marvell.com",
        "aliases": "Marvell;MRVL",
        "description": "Large semiconductor company focused on data infrastructure, networking, storage, and custom silicon.",
        "products": ["network_ic", "custom_ai_accelerator"],
    },
    {
        "rank": 60,
        "ticker": "MCHP",
        "company_id": "US_MCHP",
        "name": "Microchip Technology",
        "english_name": "Microchip Technology Incorporated",
        "exchange": "NASDAQ",
        "website": "https://www.microchip.com",
        "aliases": "Microchip;MCHP",
        "description": "Large semiconductor company focused on microcontrollers, analog IC, embedded control, and connectivity.",
        "products": ["analog_ic", "network_ic"],
    },
    {
        "rank": 61,
        "ticker": "PLTR",
        "company_id": "US_PLTR",
        "name": "Palantir",
        "english_name": "Palantir Technologies Inc.",
        "exchange": "NASDAQ",
        "website": "https://www.palantir.com",
        "aliases": "Palantir;PLTR",
        "description": "Large data analytics and AI software company serving commercial and government customers.",
        "products": ["data_analytics_software", "enterprise_software"],
    },
    {
        "rank": 62,
        "ticker": "SNOW",
        "company_id": "US_SNOW",
        "name": "Snowflake",
        "english_name": "Snowflake Inc.",
        "exchange": "NYSE",
        "website": "https://www.snowflake.com",
        "aliases": "Snowflake;SNOW",
        "description": "Large data cloud software company providing cloud data platform and analytics services.",
        "products": ["database_software", "cloud_infrastructure_service", "data_analytics_software"],
    },
]

US_UNIVERSE.extend(ADDITIONAL_US_UNIVERSE)

EXISTING_US_COMPANY_PRODUCTS = {
    "US_NVDA": ["ai_gpu", "custom_ai_accelerator"],
    "US_AMD": ["ai_gpu", "server_cpu"],
    "US_AAPL": ["smartphone", "creative_software"],
    "US_MU": ["dram", "hbm"],
    "US_NKE": ["footwear_manufacturing_service"],
    "US_BA": ["aerospace_component"],
}

PRODUCTS = [
    ("cloud_infrastructure_service", "Cloud Infrastructure Service", "Service", "IaaS;PaaS;cloud computing;AWS;Azure;Google Cloud;OCI", "提供 compute、storage、networking、AI infrastructure 的 cloud 服務。"),
    ("enterprise_software", "Enterprise Software", "Software", "SaaS;enterprise application;business software", "企業營運、資料、流程與生產力軟體。"),
    ("online_advertising_service", "Online Advertising Service", "Service", "digital ads;online ads", "搜尋、社群、影音與 display advertising 服務。"),
    ("search_engine_service", "Search Engine Service", "Service", "search engine", "網路搜尋與資訊檢索服務。"),
    ("ecommerce_marketplace", "Ecommerce Marketplace", "Service", "online marketplace;ecommerce", "線上零售與第三方 marketplace 服務。"),
    ("social_media_platform", "Social Media Platform", "Service", "social network;social app", "社群、訊息與內容平台。"),
    ("electric_vehicle", "Electric Vehicle", "End Device", "EV", "電動車整車與相關平台。"),
    ("energy_storage_system", "Energy Storage System", "Energy", "battery energy storage;BESS", "電池儲能系統與能源管理設備。"),
    ("autonomous_driving_platform", "Autonomous Driving Platform", "Software", "ADAS;self-driving", "自動駕駛與車用 AI 軟硬體平台。"),
    ("custom_ai_accelerator", "Custom AI Accelerator", "Semiconductor", "ASIC AI accelerator;custom silicon", "客製化 AI accelerator 或 ASIC 晶片。"),
    ("database_software", "Database Software", "Software", "database;DBMS", "資料庫與資料管理軟體。"),
    ("streaming_service", "Streaming Service", "Service", "video streaming;OTT", "影音串流與訂閱內容服務。"),
    ("creative_software", "Creative Software", "Software", "creative cloud;design software", "設計、影像、文件與創意工作軟體。"),
    ("cybersecurity_software", "Cybersecurity Software", "Software", "network security;security platform", "網路安全、端點安全與雲端安全平台。"),
    ("analog_ic", "Analog IC", "Semiconductor", "analog semiconductor;mixed signal", "類比與 mixed-signal IC。"),
    ("semiconductor_equipment_product", "Semiconductor Equipment", "Equipment", "wafer fabrication equipment;WFE", "晶圓製造與 semiconductor process equipment。"),
    ("mobility_platform", "Mobility Platform", "Service", "ride sharing;delivery marketplace", "叫車、外送與 mobility marketplace 平台。"),
    ("payment_network", "Payment Network", "Service", "card network;digital payments", "信用卡網路、交易處理與 digital payment infrastructure。"),
]

PRODUCTS.extend([
    ("pharmaceutical_product", "Pharmaceutical Product", "Healthcare", "medicine;drug;biopharma", "Prescription medicines, vaccines, and biopharmaceutical products."),
    ("healthcare_service", "Healthcare Service", "Service", "healthcare;care delivery;health services", "Healthcare delivery, clinical, pharmacy, and health services."),
    ("health_insurance_service", "Health Insurance Service", "Service", "managed care;health insurance", "Health insurance and managed care services."),
    ("medical_device", "Medical Device", "Healthcare", "medtech;medical equipment", "Medical devices, instruments, and treatment systems."),
    ("diagnostics_instrument", "Diagnostics Instrument", "Healthcare", "diagnostics;lab instrument", "Diagnostics instruments, tests, and laboratory equipment."),
    ("life_science_tool", "Life Science Tool", "Healthcare", "life science tools;reagent;consumable", "Life science tools, reagents, consumables, and research services."),
    ("surgical_robot", "Surgical Robot", "Healthcare", "robotic surgery;da Vinci", "Robotic-assisted surgical systems and related instruments."),
    ("oil_gas_product", "Oil and Gas Product", "Energy", "oil;natural gas;LNG", "Crude oil, natural gas, LNG, and upstream energy products."),
    ("oilfield_service", "Oilfield Service", "Service", "drilling;reservoir;production service", "Oilfield drilling, reservoir, production, and energy technology services."),
    ("industrial_software", "Industrial Software", "Software", "industrial digital;energy software", "Industrial and energy software platforms."),
    ("home_improvement_retail", "Home Improvement Retail", "Service", "home improvement;building supply retail", "Retail services for home improvement, building products, tools, and contractor supplies."),
    ("restaurant_service", "Restaurant Service", "Service", "restaurant;quick service restaurant;coffee retail", "Restaurant, quick-service restaurant, coffee retail, and franchising services."),
    ("beverage_product", "Beverage Product", "Consumer Goods", "beverage;soft drink;coffee", "Beverage concentrates, syrups, coffee, and finished beverages."),
    ("consumer_goods", "Consumer Goods", "Consumer Goods", "household goods;personal care", "Packaged consumer goods for personal care, home care, baby care, and household use."),
    ("data_analytics_software", "Data Analytics Software", "Software", "data platform;AI software;analytics", "Data analytics, AI software, data platform, and financial information software."),
    ("aerospace_defense_system", "Aerospace Defense System", "Aerospace", "defense system;missile;avionics;engine", "Aerospace and defense systems, aircraft engines, avionics, missiles, and sensors."),
    ("construction_mining_equipment", "Construction and Mining Equipment", "Equipment", "construction equipment;mining equipment", "Construction, mining, engine, turbine, and heavy equipment products."),
    ("industrial_equipment_product", "Industrial Equipment", "Equipment", "industrial equipment;machinery", "Industrial machinery, automation equipment, and engineered equipment."),
    ("industrial_automation_equipment", "Industrial Automation Equipment", "Equipment", "automation;building automation;control system", "Industrial automation, building automation, and control equipment."),
    ("agricultural_equipment", "Agricultural Equipment", "Equipment", "agriculture equipment;precision agriculture", "Agricultural equipment and precision agriculture technology."),
    ("logistics_service", "Logistics Service", "Service", "parcel delivery;logistics;supply chain", "Package delivery, freight forwarding, logistics, and supply-chain services."),
    ("railroad_service", "Railroad Service", "Service", "railroad;freight rail", "Freight railroad transportation services."),
])

US_INDUSTRIES = [
    ("software_cloud", "Software and Cloud", "", "Cloud infrastructure, enterprise software, SaaS, data analytics, and cybersecurity."),
    ("internet_platform", "Internet Platform", "", "Search, advertising, social media, ecommerce, streaming, and online marketplace platforms."),
    ("financial_services", "Financial Services", "", "Banking, payments, capital markets, asset management, and financial information services."),
    ("healthcare", "Healthcare", "", "Pharmaceuticals, medical devices, diagnostics, healthcare services, and life science tools."),
    ("energy", "Energy", "", "Oil, natural gas, refined petroleum, oilfield service, and energy technology."),
    ("retail", "Retail", "", "Physical and online retail services, wholesale clubs, and home improvement retail."),
    ("restaurants", "Restaurants", "", "Restaurant, coffee retail, and quick-service restaurant operations."),
    ("consumer_staples", "Consumer Staples", "", "Beverages, packaged food, and household consumer goods."),
    ("industrial_machinery", "Industrial Machinery", "", "Construction, mining, agriculture, automation, and heavy industrial equipment."),
    ("transportation_logistics", "Transportation and Logistics", "", "Parcel delivery, freight railroad, shipping, and logistics services."),
    ("automotive_ev", "Automotive and EV", "automotive", "Electric vehicles, automotive platforms, energy storage, and autonomous driving."),
]

PRODUCT_TO_US_INDUSTRY = {
    "cloud_infrastructure_service": "software_cloud",
    "enterprise_software": "software_cloud",
    "database_software": "software_cloud",
    "creative_software": "software_cloud",
    "cybersecurity_software": "software_cloud",
    "data_analytics_software": "software_cloud",
    "industrial_software": "software_cloud",
    "search_engine_service": "internet_platform",
    "online_advertising_service": "internet_platform",
    "ecommerce_marketplace": "internet_platform",
    "social_media_platform": "internet_platform",
    "streaming_service": "internet_platform",
    "mobility_platform": "internet_platform",
    "ai_gpu": "semiconductor",
    "custom_ai_accelerator": "semiconductor",
    "smartphone_soc": "semiconductor",
    "network_ic": "semiconductor",
    "server_cpu": "semiconductor",
    "analog_ic": "semiconductor",
    "power_management_ic": "semiconductor",
    "wafer_foundry_service": "semiconductor_foundry",
    "semiconductor_equipment_product": "semiconductor_equipment",
    "financial_service": "financial_services",
    "securities_service": "financial_services",
    "payment_network": "financial_services",
    "pharmaceutical_product": "healthcare",
    "healthcare_service": "healthcare",
    "health_insurance_service": "healthcare",
    "medical_device": "healthcare",
    "diagnostics_instrument": "healthcare",
    "life_science_tool": "healthcare",
    "surgical_robot": "healthcare",
    "oil_gas_product": "energy",
    "oilfield_service": "energy",
    "refined_petroleum": "energy",
    "petrochemical_product": "petrochemical",
    "retail_service": "retail",
    "ecommerce_service": "retail",
    "home_improvement_retail": "retail",
    "restaurant_service": "restaurants",
    "beverage_product": "consumer_staples",
    "food_beverage_product": "consumer_staples",
    "consumer_goods": "consumer_staples",
    "construction_mining_equipment": "industrial_machinery",
    "industrial_equipment_product": "industrial_machinery",
    "industrial_automation_equipment": "industrial_machinery",
    "agricultural_equipment": "industrial_machinery",
    "logistics_service": "transportation_logistics",
    "railroad_service": "transportation_logistics",
    "aerospace_component": "aerospace_defense",
    "aerospace_defense_system": "aerospace_defense",
    "electric_vehicle": "automotive_ev",
    "energy_storage_system": "automotive_ev",
    "autonomous_driving_platform": "automotive_ev",
    "smartphone": "consumer_brand",
}

TW_OFFICIAL_SOURCE_TEMPLATES = [
    (
        "annual_report_index",
        "MOPS annual report search",
        "mops",
        "https://mops.twse.com.tw/mops/web/t57sb01_q1",
        "Market Observation Post System",
        "zh-TW",
    ),
    (
        "financial_report_index",
        "MOPS financial statement search",
        "mops",
        "https://mops.twse.com.tw/mops/web/t05st10_ifrs",
        "Market Observation Post System",
        "zh-TW",
    ),
]

GLOBAL_COMPANY_OFFICIAL_SOURCES = {
    "NL_ASML": [
        ("source_asml_annual_reports", "ASML annual reports", "annual_report", "https://www.asml.com/investors/annual-report", "ASML", "en-US"),
        ("source_asml_financial_results", "ASML financial results", "financial_report", "https://www.asml.com/investors/financial-results", "ASML", "en-US"),
    ],
    "KR_005930": [
        ("source_samsung_electronics_ir", "Samsung Electronics investor relations", "company_website", "https://www.samsung.com/global/ir/", "Samsung Electronics", "en-US"),
        ("source_samsung_electronics_financial_statements", "Samsung Electronics financial statements", "financial_report", "https://www.samsung.com/global/ir/financial-information/audited-financial-statements/", "Samsung Electronics", "en-US"),
    ],
    "KR_000660": [
        ("source_skhynix_ir", "SK hynix investor relations", "company_website", "https://www.skhynix.com/ir/UI-FR-IR01/", "SK hynix", "en-US"),
        ("source_skhynix_financial_statements", "SK hynix financial statements", "financial_report", "https://www.skhynix.com/ir/UI-FR-IR07/", "SK hynix", "en-US"),
    ],
}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_sec_exchange_index() -> dict[str, dict]:
    data = get_json("https://www.sec.gov/files/company_tickers_exchange.json")
    fields = data["fields"]
    ticker_index = fields.index("ticker")
    return {row[ticker_index].upper(): dict(zip(fields, row)) for row in data["data"]}


def sec_submission(cik: str) -> dict:
    return get_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")


def latest_filing(submission: dict, form: str) -> dict[str, str] | None:
    recent = submission.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    for i, current_form in enumerate(forms):
        if current_form == form:
            cik = str(submission["cik"])
            accession = recent["accessionNumber"][i]
            primary_doc = recent["primaryDocument"][i]
            accession_path = accession.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_path}/{primary_doc}"
            report_date = recent.get("reportDate", [""] * len(forms))[i]
            filing_date = recent.get("filingDate", [""] * len(forms))[i]
            return {
                "form": form,
                "accession": accession,
                "primary_document": primary_doc,
                "url": url,
                "report_date": report_date,
                "filing_date": filing_date,
                "period": report_date[:4] if report_date else filing_date[:4],
            }
    return None


def add_unique(rows: list[dict[str, str]], key: str, new_rows: list[dict[str, str]]) -> int:
    existing = {row.get(key, "") for row in rows}
    added = 0
    for row in new_rows:
        if row[key] not in existing:
            rows.append(row)
            existing.add(row[key])
            added += 1
    return added


PROGRESS_STATUS_RANK = {
    "company_seed_present": 0,
    "official_sources_registered": 1,
    "official_source_index_registered": 1,
    "documents_indexed": 2,
    "candidate_relationships_loaded": 3,
    "relationships_extracted": 3,
    "reviewed_verified": 4,
}


def merge_existing_progress(new_rows: list[dict[str, str]], existing_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Preserve deeper progress while allowing source refresh fields to advance."""
    existing_by_id = {row.get("company_id", ""): row for row in existing_rows}
    preserve_when_deeper = {
        "status",
        "last_updated_at",
        "data_depth",
        "relationship_depth",
        "next_action",
        "notes",
    }
    source_fields = {
        "last_source_refresh_at",
        "latest_annual_source_id",
        "latest_quarterly_source_id",
    }

    merged = []
    for row in new_rows:
        old = existing_by_id.get(row.get("company_id", ""))
        if not old:
            merged.append(row)
            continue

        for field in source_fields:
            if not row.get(field) and old.get(field):
                row[field] = old[field]

        old_rank = PROGRESS_STATUS_RANK.get(old.get("status", ""), -1)
        new_rank = PROGRESS_STATUS_RANK.get(row.get("status", ""), -1)
        if old_rank > new_rank:
            for field in preserve_when_deeper:
                if old.get(field):
                    row[field] = old[field]

        merged.append(row)
    return merged


def build_us_universe(companies: list[dict[str, str]]) -> list[dict[str, str]]:
    """Merge curated US universe with already-seeded US companies.

    Existing seed companies such as NVIDIA/AMD/Apple predate this workflow. They
    still need SEC source refresh and progress tracking, so include them here
    without forcing duplicate company rows.
    """
    by_id = {row["company_id"]: dict(row) for row in US_UNIVERSE}
    next_rank = len(by_id) + 1
    for company in companies:
        company_id = company.get("id", "")
        if not company_id.startswith("US_") or company_id in by_id:
            continue
        ticker = company.get("ticker", "")
        if not ticker:
            continue
        by_id[company_id] = {
            "rank": next_rank,
            "ticker": ticker,
            "company_id": company_id,
            "name": company.get("name") or company.get("english_name") or ticker,
            "english_name": company.get("english_name") or company.get("name") or ticker,
            "exchange": company.get("exchange") or "US",
            "website": company.get("website") or "",
            "aliases": company.get("aliases") or ticker,
            "description": company.get("description") or "Seeded US company; official SEC sources are tracked for enrichment.",
            "products": EXISTING_US_COMPANY_PRODUCTS.get(company_id, []),
        }
        next_rank += 1
    return sorted(by_id.values(), key=lambda row: int(row["rank"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write seed/progress CSV updates.")
    parser.add_argument("--skip-sec", action="store_true", help="Do not call SEC; use static universe only.")
    args = parser.parse_args()

    sec_index = {} if args.skip_sec else load_sec_exchange_index()

    companies_path = SEEDS / "seed_companies.csv"
    sources_path = SEEDS / "seed_sources.csv"
    products_path = SEEDS / "seed_products.csv"
    industries_path = SEEDS / "seed_industries.csv"
    relationships_path = SEEDS / "seed_relationships.csv"
    tw_universe_path = SEEDS / "universe_tw_top100.csv"
    us_universe_path = SEEDS / "universe_us_large_cap.csv"
    progress_path = PROGRESS / "company_update_progress.csv"

    companies = read_csv(companies_path)
    sources = read_csv(sources_path)
    products = read_csv(products_path)
    industries = read_csv(industries_path)
    relationships = read_csv(relationships_path)
    tw_universe = read_csv(tw_universe_path)
    all_company_ids = {row.get("id", "") for row in companies}
    progress_company_ids: set[str] = set()
    us_universe = build_us_universe(companies)

    company_fields = list(companies[0].keys())
    source_fields = list(sources[0].keys())
    product_fields = list(products[0].keys())
    industry_fields = list(industries[0].keys())
    relationship_fields = list(relationships[0].keys())

    new_companies = []
    new_sources = [
        {
            "id": "source_sec_company_tickers_exchange",
            "title": "SEC company_tickers_exchange.json",
            "type": "exchange_data",
            "url": "https://www.sec.gov/files/company_tickers_exchange.json",
            "publisher": "U.S. Securities and Exchange Commission",
            "published_date": "",
            "retrieved_at": TODAY,
            "company_id": "",
            "period": TODAY[:4],
            "language": "en-US",
        },
        {
            "id": "source_twse_2025_factbook_top_market_cap",
            "title": "TWSE Fact Book 2025 - Top Companies by Market Capitalization",
            "type": "exchange_data",
            "url": "https://www.twse.com.tw/downloads/zh/about/company/factbook/2025/1.04.html",
            "publisher": "Taiwan Stock Exchange",
            "published_date": "",
            "retrieved_at": TODAY,
            "company_id": "",
            "period": "2024",
            "language": "en-US",
        },
    ]
    new_relationships = []
    progress_rows = []
    us_universe_rows = []

    product_rows = [
        {
            "id": pid,
            "name": name,
            "category": category,
            "aliases": aliases,
            "description": desc,
            "parent_product_id": "",
        }
        for pid, name, category, aliases, desc in PRODUCTS
    ]
    industry_rows = [
        {
            "id": industry_id,
            "name": name,
            "parent_industry_id": parent_id,
            "description": desc,
        }
        for industry_id, name, parent_id, desc in US_INDUSTRIES
    ]

    for company in us_universe:
        ticker = company["ticker"]
        sec_meta = sec_index.get(ticker, {})
        cik = str(sec_meta.get("cik") or "")
        sec_exchange = sec_meta.get("exchange") or company["exchange"]
        sec_name = sec_meta.get("name") or company["english_name"]
        latest_10k = latest_10q = None
        submissions_source_id = f"source_sec_{ticker.lower()}_submissions"

        if cik and not args.skip_sec:
            time.sleep(0.12)
            submission = sec_submission(cik)
            latest_10k = latest_filing(submission, "10-K")
            latest_10q = latest_filing(submission, "10-Q")
            new_sources.append({
                "id": submissions_source_id,
                "title": f"{ticker} SEC submissions JSON",
                "type": "exchange_data",
                "url": f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                "publisher": "U.S. Securities and Exchange Commission",
                "published_date": "",
                "retrieved_at": TODAY,
                "company_id": company["company_id"],
                "period": TODAY[:4],
                "language": "en-US",
            })
            for filing, source_type in ((latest_10k, "annual_report"), (latest_10q, "financial_report")):
                if not filing:
                    continue
                form_slug = filing["form"].lower().replace("-", "")
                source_id = f"source_sec_{ticker.lower()}_{filing['period']}_{form_slug}"
                filing["source_id"] = source_id
                new_sources.append({
                    "id": source_id,
                    "title": f"{company['english_name']} latest SEC {filing['form']}",
                    "type": source_type,
                    "url": filing["url"],
                    "publisher": "U.S. Securities and Exchange Commission",
                    "published_date": filing["filing_date"],
                    "retrieved_at": TODAY,
                    "company_id": company["company_id"],
                    "period": filing["period"],
                    "language": "en-US",
                })

        source_for_relationships = (latest_10k or {}).get("source_id") or submissions_source_id
        for product_id in company["products"]:
            rel_type = "PRODUCES" if product_id in {
                "smartphone_soc", "network_ic", "server_cpu", "wafer_foundry_service",
                "analog_ic", "semiconductor_equipment_product", "electric_vehicle",
                "energy_storage_system", "custom_ai_accelerator",
            } else "SELLS"
            new_relationships.append({
                "id": f"rel_us_{ticker.lower()}_{rel_type.lower()}_{product_id}",
                "from_id": company["company_id"],
                "to_id": product_id,
                "type": rel_type,
                "description": f"{company['name']} {rel_type.lower()} {product_id.replace('_', ' ')}; source is latest official SEC filing metadata.",
                "product_id": product_id,
                "confidence": "0.75",
                "status": "candidate",
                "value": "",
                "unit": "",
                "value_type": "reported",
                "period": (latest_10k or {}).get("period") or TODAY[:4],
                "valid_from": "",
                "valid_to": "",
                "source_ids": source_for_relationships,
                "note": "agent curated from official SEC filing index; review before verified",
            })

        industry_id = next(
            (PRODUCT_TO_US_INDUSTRY[product_id] for product_id in company["products"] if product_id in PRODUCT_TO_US_INDUSTRY),
            "",
        )
        if industry_id:
            new_relationships.append({
                "id": f"rel_us_{ticker.lower()}_belongs_to_{industry_id}",
                "from_id": company["company_id"],
                "to_id": industry_id,
                "type": "BELONGS_TO",
                "description": f"{company['name']} is classified in {industry_id.replace('_', ' ')} based on curated product/service exposure and official SEC source metadata.",
                "product_id": "",
                "confidence": "0.75",
                "status": "candidate",
                "value": "",
                "unit": "",
                "value_type": "reported",
                "period": (latest_10k or {}).get("period") or TODAY[:4],
                "valid_from": "",
                "valid_to": "",
                "source_ids": source_for_relationships,
                "note": "agent curated industry classification from official SEC filing index; review before verified",
            })

        if company["company_id"] not in all_company_ids:
            new_companies.append({
                "id": company["company_id"],
                "name": company["name"],
                "english_name": sec_name,
                "ticker": ticker,
                "exchange": sec_exchange,
                "country": "US",
                "is_listed_in_tw": "false",
                "aliases": company["aliases"],
                "website": company["website"],
                "description": company["description"],
                "snapshot_date": TODAY,
            })
        us_universe_rows.append({
            "rank": str(company["rank"]),
            "company_id": company["company_id"],
            "ticker": ticker,
            "name": company["name"],
            "english_name": sec_name,
            "exchange": sec_exchange,
            "country": "US",
            "universe_type": "US_LARGE_CAP_RESEARCH_UNIVERSE",
            "snapshot_date": TODAY,
            "source": "source_sec_company_tickers_exchange",
            "cik": cik,
            "note": "Curated large US companies relevant for AI, cloud, semiconductor, software, payment, retail, and platform analysis.",
        })
        progress_company_ids.add(company["company_id"])
        progress_rows.append({
            "company_id": company["company_id"],
            "ticker": ticker,
            "exchange": sec_exchange,
            "name": company["name"],
            "universe_type": "US_LARGE_CAP_RESEARCH_UNIVERSE",
            "priority": "high",
            "status": "official_sources_registered",
            "last_updated_at": TODAY,
            "last_source_refresh_at": TODAY,
            "latest_annual_source_id": (latest_10k or {}).get("source_id", ""),
            "latest_quarterly_source_id": (latest_10q or {}).get("source_id", ""),
            "data_depth": "company+latest_sec_sources+candidate_product_edges",
            "relationship_depth": "core_product_exposure_only" if company["products"] else "source_only",
            "next_action": "download/parse latest 10-K and 10-Q, extract supply/customer/product/application relationships as candidate",
            "notes": "Use official SEC sources; keep extracted relationships candidate until reviewed.",
        })

    for tw in tw_universe:
        annual_source_id = f"source_mops_{tw['company_id'].lower()}_annual_report_index"
        quarterly_source_id = f"source_mops_{tw['company_id'].lower()}_financial_report_index"
        for suffix, title, source_type, url, publisher, language in TW_OFFICIAL_SOURCE_TEMPLATES:
            source_id = f"source_mops_{tw['company_id'].lower()}_{suffix}"
            new_sources.append({
                "id": source_id,
                "title": f"{tw['ticker']} {title}",
                "type": source_type,
                "url": url,
                "publisher": publisher,
                "published_date": "",
                "retrieved_at": TODAY,
                "company_id": tw["company_id"],
                "period": TODAY[:4],
                "language": language,
            })
        progress_company_ids.add(tw["company_id"])
        progress_rows.append({
            "company_id": tw["company_id"],
            "ticker": tw["ticker"],
            "exchange": tw["exchange"],
            "name": tw["name"],
            "universe_type": tw["universe_type"],
            "priority": "high" if int(tw["rank"]) <= 30 else "medium",
            "status": "official_source_index_registered",
            "last_updated_at": TODAY,
            "last_source_refresh_at": TODAY,
            "latest_annual_source_id": annual_source_id,
            "latest_quarterly_source_id": quarterly_source_id,
            "data_depth": "company_seed+mops_source_index; some manual_seed relationships",
            "relationship_depth": "varies_by_company",
            "next_action": "fetch latest annual report and financial report from MOPS/company IR, then extract candidate relationships",
            "notes": f"Rank {tw['rank']} in existing TW top100 universe. Refresh universe source against TWSE/Taiwan Index provider before major updates.",
        })

    company_by_id = {company.get("id", ""): company for company in companies}
    for company_id, source_defs in GLOBAL_COMPANY_OFFICIAL_SOURCES.items():
        company = company_by_id.get(company_id)
        if not company:
            continue
        for source_id, title, source_type, url, publisher, language in source_defs:
            new_sources.append({
                "id": source_id,
                "title": title,
                "type": source_type,
                "url": url,
                "publisher": publisher,
                "published_date": "",
                "retrieved_at": TODAY,
                "company_id": company_id,
                "period": TODAY[:4],
                "language": language,
            })
        progress_company_ids.add(company_id)
        progress_rows.append({
            "company_id": company_id,
            "ticker": company.get("ticker", ""),
            "exchange": company.get("exchange", ""),
            "name": company.get("name", ""),
            "universe_type": "GLOBAL_SEEDED_COMPANY",
            "priority": "medium",
            "status": "official_source_index_registered",
            "last_updated_at": TODAY,
            "last_source_refresh_at": TODAY,
            "latest_annual_source_id": source_defs[0][0],
            "latest_quarterly_source_id": source_defs[1][0] if len(source_defs) > 1 else "",
            "data_depth": "company_seed+official_source_index",
            "relationship_depth": "varies_by_company",
            "next_action": "download/parse latest annual and quarterly reports, then extract candidate relationships",
            "notes": "Official IR source index registered by enrichment workflow.",
        })

    for company in companies:
        company_id = company.get("id", "")
        if not company_id or company_id in progress_company_ids:
            continue
        progress_rows.append({
            "company_id": company_id,
            "ticker": company.get("ticker", ""),
            "exchange": company.get("exchange", ""),
            "name": company.get("name", ""),
            "universe_type": "SEEDED_COMPANY_NOT_IN_PRIMARY_UNIVERSE",
            "priority": "medium",
            "status": "company_seed_present",
            "last_updated_at": "",
            "last_source_refresh_at": "",
            "latest_annual_source_id": "",
            "latest_quarterly_source_id": "",
            "data_depth": "company_seed",
            "relationship_depth": "varies_by_company",
            "next_action": "assign to TW/US/global universe, register official sources, then extract candidate relationships",
            "notes": "Automatically tracked because it exists in seed_companies.csv.",
        })

    added = {
        "companies": add_unique(companies, "id", new_companies),
        "sources": add_unique(sources, "id", new_sources),
        "products": add_unique(products, "id", product_rows),
        "industries": add_unique(industries, "id", industry_rows),
        "relationships": add_unique(relationships, "id", new_relationships),
    }
    progress_rows = merge_existing_progress(progress_rows, read_csv(progress_path))

    print("Planned/appended rows:", added)
    print(f"US universe rows: {len(us_universe_rows)}")
    print(f"Progress rows: {len(progress_rows)}")

    if args.write:
        write_csv(companies_path, company_fields, companies)
        write_csv(sources_path, source_fields, sources)
        write_csv(products_path, product_fields, products)
        write_csv(industries_path, industry_fields, industries)
        write_csv(relationships_path, relationship_fields, relationships)
        write_csv(us_universe_path, [
            "rank", "company_id", "ticker", "name", "english_name", "exchange",
            "country", "universe_type", "snapshot_date", "source", "cik", "note",
        ], us_universe_rows)
        write_csv(progress_path, [
            "company_id", "ticker", "exchange", "name", "universe_type", "priority",
            "status", "last_updated_at", "last_source_refresh_at",
            "latest_annual_source_id", "latest_quarterly_source_id", "data_depth",
            "relationship_depth", "next_action", "notes",
        ], progress_rows)
    else:
        print("Dry run only. Re-run with --write to update CSV files.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
