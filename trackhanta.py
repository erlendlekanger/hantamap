"""
Track Hanta style dashboard (privacy-safe).

This app intentionally tracks aggregate case metrics (by region/country)
instead of identifiable people.

Run:
  python trackhanta.py

Open:
  http://127.0.0.1:8787/
"""

from __future__ import annotations

import http.server
import json
import re
import socketserver
import time
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

PORT = 8787
POLYMARKET_URL = "https://polymarket.com/event/hantavirus-pandemic-in-2026"
POLYMARKET_REFRESH_SECONDS = 120
POLYMARKET_UA = "Mozilla/5.0 (TrackHantaBot/1.0; +https://localhost)"
NEWS_FEED_URL = "https://news.google.com/rss/search?q=hantavirus&hl=en-US&gl=US&ceid=US:en"
NEWS_REFRESH_SECONDS = 120
LOGO_PATH = Path(__file__).resolve().parent / "trackhanta_logo_white.png"
FAVICON_PATH = Path(__file__).resolve().parent / "trackhanta_favicon.ico"
FAVICON_PNG_PATH = Path(__file__).resolve().parent / "trackhanta_favicon.png"
FAVICON_DARK_PATH = Path(__file__).resolve().parent / "trackhanta_favicon_dark.ico"
FAVICON_DARK_PNG_PATH = Path(__file__).resolve().parent / "trackhanta_favicon_dark.png"

POLYMARKET_CACHE = {
    "odds_yes_pct": None,
    "fetched_at": None,
    "error": "Not fetched yet.",
    "cache_age_seconds": None,
}
NEWS_CACHE = {
    "items": [],
    "fetched_at": None,
    "error": None,
}

CASES = [
    {
        "region": "Bariloche",
        "country": "Argentina",
        "country_code": "AR",
        "lat": -41.1335,
        "lon": -71.3103,
        "confirmed": 38,
        "suspected": 12,
        "recovered": 29,
        "deceased": 4,
        "risk": "High",
        "signal": "Cluster in Andean foothill communities under investigation.",
        "last_update": "2026-05-07T07:40:00Z",
    },
    {
        "region": "Temuco",
        "country": "Chile",
        "country_code": "CL",
        "lat": -38.7359,
        "lon": -72.5904,
        "confirmed": 26,
        "suspected": 9,
        "recovered": 20,
        "deceased": 2,
        "risk": "Moderate",
        "signal": "Mostly rural exposure linked to rodent-heavy zones.",
        "last_update": "2026-05-07T06:15:00Z",
    },
    {
        "region": "Santa Cruz",
        "country": "Bolivia",
        "country_code": "BO",
        "lat": -17.7833,
        "lon": -63.1821,
        "confirmed": 11,
        "suspected": 6,
        "recovered": 8,
        "deceased": 1,
        "risk": "Moderate",
        "signal": "Case growth stable over last 7 days.",
        "last_update": "2026-05-07T08:10:00Z",
    },
    {
        "region": "Las Tablas",
        "country": "Panama",
        "country_code": "PA",
        "lat": 7.7647,
        "lon": -80.2736,
        "confirmed": 9,
        "suspected": 3,
        "recovered": 7,
        "deceased": 0,
        "risk": "Low",
        "signal": "Isolated reports, no sustained surge detected.",
        "last_update": "2026-05-07T09:00:00Z",
    },
]

INCIDENTS = [
    {
        "type": "death",
        "title": "Death reported on MV Hondius (Dutch male, age 70)",
        "location": "South Atlantic between South Georgia and St. Helena",
        "lat": -27.5,
        "lon": -20.0,
        "date": "2026-04-11",
        "details": "Became ill after departure and died on board while ship was in the South Atlantic.",
        "source": "AP / WHO timeline",
    },
    {
        "type": "death",
        "title": "Death reported after evacuation (Dutch female, age 69)",
        "location": "Johannesburg hospital, South Africa",
        "lat": -26.2041,
        "lon": 28.0473,
        "date": "2026-04-26",
        "details": "Collapsed after flight from St. Helena and died in hospital. Later PCR-confirmed positive in South Africa.",
        "source": "AP / WHO timeline",
    },
    {
        "type": "death",
        "title": "Death reported on ship (German female)",
        "location": "Atlantic waters west of Cape Verde",
        "lat": 13.0,
        "lon": -27.0,
        "date": "2026-05-02",
        "details": "Died on board after severe respiratory symptoms while vessel was en route toward Cape Verde.",
        "source": "AP / WHO timeline",
    },
    {
        "type": "confirmed",
        "title": "Lab-confirmed case: British male (ICU)",
        "location": "South Africa (NICD-linked testing)",
        "lat": -26.2041,
        "lon": 28.0473,
        "date": "2026-05-03",
        "details": "Evacuated from Ascension Island route to South Africa and confirmed positive by lab testing.",
        "source": "AP / WHO timeline",
    },
    {
        "type": "confirmed",
        "title": "Lab confirmation: Dutch female postmortem PCR",
        "location": "South Africa (NICD)",
        "lat": -26.2041,
        "lon": 28.0473,
        "date": "2026-05-04",
        "details": "Postmortem PCR reported positive in South Africa on May 4.",
        "source": "AP / WHO timeline",
    },
    {
        "type": "confirmed",
        "title": "Lab-confirmed case: Swiss male",
        "location": "Zurich, Switzerland",
        "lat": 47.3769,
        "lon": 8.5417,
        "date": "2026-05-06",
        "details": "Positive result reported after earlier disembarkation from voyage.",
        "source": "AP / WHO timeline",
    },
    {
        "type": "confirmed",
        "title": "Lab-confirmed evacuee case(s) in Netherlands",
        "location": "Amsterdam, Netherlands",
        "lat": 52.3676,
        "lon": 4.9041,
        "date": "2026-05-06",
        "details": "Two or more among medical evacuees to the Netherlands were reported as lab-confirmed.",
        "source": "Multi-source media summary",
    },
    {
        "type": "confirmed",
        "title": "Additional confirmed evacuee-linked case",
        "location": "Amsterdam, Netherlands",
        "lat": 52.3676,
        "lon": 4.9041,
        "date": "2026-05-06",
        "details": "Second plotted confirmation marker for evacuee positives reported in the Netherlands.",
        "source": "Multi-source media summary",
    },
    {
        "type": "suspected",
        "title": "Suspected/monitoring cluster in ship quarantine",
        "location": "Cape Verde waters",
        "lat": 14.9,
        "lon": -23.5,
        "date": "2026-05-06",
        "details": "Passengers and crew remained isolated in cabins while monitoring and contact tracing continued.",
        "source": "AP / WHO timeline",
    },
    {
        "type": "suspected",
        "title": "Asymptomatic close contact under testing",
        "location": "Dusseldorf, Germany",
        "lat": 51.2277,
        "lon": 6.7735,
        "date": "2026-05-06",
        "details": "Asymptomatic contact linked to a fatal case was sent for hospital testing.",
        "source": "Multi-source media summary",
    },
    {
        "type": "suspected",
        "title": "Onboard suspect case pool",
        "location": "En route to Canary Islands",
        "lat": 21.0,
        "lon": -20.5,
        "date": "2026-05-07",
        "details": "Overall ship-linked total reported around 8 cases (confirmed + suspected) with continued follow-up.",
        "source": "Multi-source media summary",
    },
]


def _build_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Hanta Map</title>
  <link rel="icon" type="image/png" sizes="64x64" href="/favicon-dark.png?v=1" />
  <link rel="icon" type="image/x-icon" href="/favicon-dark.ico?v=1" />
  <link rel="shortcut icon" href="/favicon-dark.ico?v=1" />
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
    html, body {
      height: 100%;
      background: #111315;
    }
    :root {
      --bg: #050b16;
      --panel: #0d1a30;
      --panel-2: #0a1426;
      --line: #1a315c;
      --text: #eaf1ff;
      --muted: #9fb7e5;
      --high: #ff5f6d;
      --mod: #ffbb3b;
      --low: #49d29b;
      --live: #34d3ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at 10% -10%, #173567 0%, var(--bg) 40%);
      color: var(--text);
      font-family: Inter, Segoe UI, Roboto, Arial, sans-serif;
    }
    .wrap {
      width: min(1500px, 100vw);
      margin: 0 auto;
      padding: 14px;
      min-height: 100vh;
    }
    .topbar {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 18px;
    }
    .topbar-right {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .support-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 9px;
      border: 1px solid #2f5c8f;
      border-radius: 999px;
      background: #0a223c;
      color: #b7d8ff;
      font-size: 11px;
      line-height: 1.2;
      max-width: 460px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .support-pill strong {
      color: #e2f1ff;
      font-weight: 700;
    }
    .brand-logo {
      height: 62px;
      width: auto;
      max-width: min(420px, 70vw);
      object-fit: contain;
      filter: drop-shadow(0 0 10px rgba(255, 255, 255, 0.15));
    }
    .live {
      display: inline-flex; align-items: center; gap: 8px; font-size: 13px;
      color: var(--live); border: 1px solid #1d5b7a; border-radius: 999px; padding: 6px 10px;
      background: #0a2536;
    }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--live); box-shadow: 0 0 10px var(--live); }
    .live-market {
      margin: 0 0 10px;
      border: 1px solid #234c7e;
      border-radius: 16px;
      padding: 14px;
      background:
        radial-gradient(circle at 90% 18%, rgba(52, 211, 255, 0.14) 0%, rgba(52, 211, 255, 0) 40%),
        radial-gradient(circle at 12% 80%, rgba(255, 168, 0, 0.08) 0%, rgba(255, 168, 0, 0) 45%),
        linear-gradient(140deg, #0a1730 0%, #0b1323 50%, #0f1526 100%);
      box-shadow: 0 0 0 1px rgba(52, 211, 255, 0.08), inset 0 0 40px rgba(52, 211, 255, 0.05);
    }
    .live-market-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }
    .live-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid #276ca2;
      background: #0a2b45;
      color: #80ddff;
      font-size: 12px;
      letter-spacing: 0.6px;
      font-weight: 700;
    }
    .live-pill-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #34d3ff;
      box-shadow: 0 0 6px #34d3ff, 0 0 12px rgba(52, 211, 255, 0.8);
      animation: pulse 1.4s infinite ease-in-out;
    }
    .odds-row {
      margin-top: 12px;
      display: grid;
      place-items: center;
      text-align: center;
      gap: 6px;
      padding: 14px 10px;
      border: 1px solid #264567;
      border-radius: 12px;
      background:
        linear-gradient(180deg, rgba(9, 25, 45, 0.85), rgba(8, 18, 34, 0.85));
    }
    .odds-main {
      font-size: clamp(34px, 5vw, 54px);
      line-height: 1;
      font-weight: 900;
      color: #ebf9ff;
      letter-spacing: 0.6px;
      text-shadow: 0 0 16px rgba(52, 211, 255, 0.24);
    }
    #poly-odds {
      color: #ff7b86;
      text-shadow:
        0 0 8px rgba(255, 77, 103, 0.75),
        0 0 18px rgba(255, 77, 103, 0.55),
        0 0 30px rgba(255, 77, 103, 0.3);
      animation: dangerPulse 1.9s ease-in-out infinite;
    }
    .odds-sub {
      color: #9dc4e7;
      font-size: 13px;
      letter-spacing: 0.8px;
      text-transform: uppercase;
    }
    .odds-meta {
      margin-top: 8px;
      color: #83a8c9;
      font-size: 12px;
    }
    .odds-link {
      color: #7bd6ff;
      text-decoration: none;
    }
    .odds-link:hover { text-decoration: underline; }
    @keyframes pulse {
      0%, 100% { transform: scale(0.9); opacity: 0.8; }
      50% { transform: scale(1.15); opacity: 1; }
    }
    @keyframes dangerPulse {
      0%, 100% {
        filter: brightness(0.98);
        text-shadow:
          0 0 7px rgba(255, 77, 103, 0.6),
          0 0 16px rgba(255, 77, 103, 0.45),
          0 0 25px rgba(255, 77, 103, 0.24);
      }
      50% {
        filter: brightness(1.14);
        text-shadow:
          0 0 10px rgba(255, 95, 118, 0.85),
          0 0 22px rgba(255, 95, 118, 0.62),
          0 0 36px rgba(255, 95, 118, 0.34);
      }
    }
    .grid { display: grid; gap: 10px; grid-template-columns: 1fr; }
    .card {
      background: linear-gradient(180deg, var(--panel), var(--panel-2));
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      min-height: 84px;
    }
    .fatal-card {
      border: 1px solid #1e4674;
      background:
        radial-gradient(circle at 92% 15%, rgba(52, 211, 255, 0.18) 0%, rgba(52, 211, 255, 0) 40%),
        linear-gradient(180deg, #0e1d36, #0a1428);
      box-shadow: 0 0 0 1px rgba(52, 211, 255, 0.1), inset 0 0 26px rgba(52, 211, 255, 0.08);
      position: relative;
      padding: 12px;
    }
    .fatal-top {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 10px;
      text-align: center;
    }
    .fatal-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 10px;
      border-radius: 999px;
      border: 1px solid #2f6d8a;
      background: #0e2a37;
      color: #9ce8ff;
      font-size: 11px;
      letter-spacing: 0.6px;
      font-weight: 700;
      position: absolute;
      right: 12px;
      top: 10px;
    }
    .fatal-skull {
      font-size: 18px;
      color: #72dfff;
      text-shadow: 0 0 10px rgba(114, 223, 255, 0.85);
    }
    .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .6px; }
    .value { margin-top: 10px; font-size: 30px; font-weight: 700; }
    .fatal-value {
      color: #8fe8ff;
      text-shadow:
        0 0 9px rgba(80, 213, 255, 0.75),
        0 0 18px rgba(80, 213, 255, 0.45);
      font-size: clamp(34px, 5vw, 48px);
      line-height: 1;
      margin-top: 8px;
      text-align: center;
    }
    .sub { margin-top: 6px; color: var(--muted); font-size: 12px; }
    .panels {
      margin-top: 10px;
      display: grid; gap: 12px;
      grid-template-columns: 1fr;
    }
    .timeline-panel {
      margin-top: 10px;
      border: 1px solid #1b3f68;
      border-radius: 12px;
      padding: 10px 12px;
      background: linear-gradient(180deg, #0d1a30, #0a1426);
    }
    .timeline-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
      font-size: 12px;
      color: #a7c3ec;
    }
    .timeline-date {
      color: #c9e5ff;
      font-weight: 700;
    }
    .timeline-input {
      width: 100%;
      accent-color: #4fcaff;
      cursor: pointer;
      appearance: none;
      height: 6px;
      border-radius: 999px;
      background: linear-gradient(90deg, #14375f, #2a7ab7);
      outline: none;
    }
    .timeline-input::-webkit-slider-thumb {
      appearance: none;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      border: 2px solid #9ce8ff;
      background: #0d2c4b;
      box-shadow: 0 0 10px rgba(80, 213, 255, 0.5);
      transition: transform 120ms ease, box-shadow 120ms ease;
    }
    .timeline-input::-webkit-slider-thumb:active {
      transform: scale(1.1);
      box-shadow: 0 0 14px rgba(80, 213, 255, 0.7);
    }
    .timeline-input::-moz-range-thumb {
      width: 18px;
      height: 18px;
      border-radius: 50%;
      border: 2px solid #9ce8ff;
      background: #0d2c4b;
      box-shadow: 0 0 10px rgba(80, 213, 255, 0.5);
    }
    .timeline-meta {
      margin-top: 6px;
      font-size: 12px;
      color: #9bb6df;
      text-align: right;
    }
    .panel {
      background: linear-gradient(180deg, var(--panel), var(--panel-2));
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
    }
    .panel h2 { margin: 0 0 12px; font-size: 15px; color: #cae0ff; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { border-bottom: 1px solid #16305f; padding: 9px 6px; text-align: left; }
    th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .6px; }
    .risk { display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
    .risk.High { color: #ffd5d9; background: #5e1f30; border: 1px solid #a7304c; }
    .risk.Moderate { color: #ffe8bf; background: #4f3b11; border: 1px solid #9a6b08; }
    .risk.Low { color: #ceffeb; background: #134734; border: 1px solid #21785a; }
    .notice {
      margin-top: 12px; color: #a9c1ea; font-size: 12px;
      border-left: 3px solid #2f5ca6; padding: 8px 10px; background: #0a1830; border-radius: 6px;
    }
    .feed { display: grid; gap: 8px; max-height: 240px; overflow-y: auto; }
    .item { border: 1px solid #173666; border-radius: 9px; padding: 10px; background: #0a1730; }
    .item .meta { display: flex; justify-content: space-between; color: var(--muted); font-size: 12px; }
    .item .title { margin-top: 6px; font-size: 14px; font-weight: 600; }
    #map {
      width: 100%;
      height: 82vh;
      min-height: 680px;
      border: 1px solid #16305f;
      border-radius: 10px;
      overflow: hidden;
      background: #121416;
    }
    .leaflet-container {
      background: #121416 !important;
    }
    .leaflet-pane,
    .leaflet-map-pane,
    .leaflet-tile-pane {
      background: #121416 !important;
    }
    .leaflet-tile {
      background: #121416 !important;
    }
    .legend {
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
    }
    .legend i {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 6px;
    }
    .leaflet-control-zoom a {
      background-color: #1a1a1a !important;
      color: #d0d0d0 !important;
      border-color: #2f2f2f !important;
    }
    .leaflet-control-zoom a:hover {
      background-color: #252525 !important;
      color: #ffffff !important;
    }
    .leaflet-control-attribution {
      background: rgba(10, 10, 10, 0.68) !important;
      color: #9e9e9e !important;
    }
    .leaflet-popup-content-wrapper, .leaflet-popup-tip {
      background: #121212;
      color: #e6e6e6;
      border: 1px solid #2f2f2f;
    }
    .incident-dot {
      width: 14px;
      height: 14px;
      border-radius: 50%;
      border: 2px solid rgba(255,255,255,0.7);
    }
    .incident-dot.confirmed {
      background: #ff3e53;
      box-shadow: 0 0 8px rgba(255, 62, 83, 0.9), 0 0 16px rgba(255, 62, 83, 0.5);
    }
    .incident-dot.suspected {
      background: #ffc93c;
      box-shadow: 0 0 8px rgba(255, 201, 60, 0.85), 0 0 14px rgba(255, 201, 60, 0.45);
    }
    .incident-skull {
      color: #ff5b6b;
      font-size: 22px;
      line-height: 1;
      text-shadow: 0 0 10px rgba(255, 91, 107, 0.95), 0 0 18px rgba(255, 91, 107, 0.55);
      transform: translate(-9px, -12px);
      user-select: none;
    }
    .popup-title { font-size: 14px; font-weight: 700; margin-bottom: 6px; }
    .popup-row { font-size: 12px; margin: 2px 0; color: #bfd3f7; }
    .news-list {
      display: grid;
      gap: 8px;
      max-height: 360px;
      min-height: 220px;
      overflow-y: auto;
      padding-right: 2px;
      scrollbar-width: thin;
      scrollbar-color: #2b6fa8 #0b182d;
    }
    .news-list::-webkit-scrollbar {
      width: 10px;
    }
    .news-list::-webkit-scrollbar-track {
      background: #0b182d;
      border-radius: 999px;
      border: 1px solid #163458;
    }
    .news-list::-webkit-scrollbar-thumb {
      background: linear-gradient(180deg, #2f8fd6, #1c5e95);
      border-radius: 999px;
      border: 1px solid #4baef2;
    }
    .news-list::-webkit-scrollbar-thumb:hover {
      background: linear-gradient(180deg, #47a7ee, #2a77b8);
    }
    .news-item {
      border: 1px solid #1c3e6e;
      border-radius: 10px;
      padding: 10px;
      background: linear-gradient(180deg, #0d1b33, #0a1529);
    }
    .news-item a {
      color: #d8ecff;
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
      line-height: 1.35;
    }
    .news-item a:hover { color: #84d9ff; }
    .news-meta {
      margin-top: 6px;
      color: #8eaed8;
      font-size: 11px;
      display: flex;
      justify-content: space-between;
      gap: 8px;
    }
    .news-state {
      color: #9bbce2;
      font-size: 12px;
      border: 1px dashed #2a4f7f;
      border-radius: 8px;
      padding: 10px;
      text-align: center;
    }
    @media (max-width: 920px) {
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 560px) {
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <img class="brand-logo" src="/assets/trackhanta-logo-white.png" alt="Track Hanta" />
      <div class="topbar-right">
        <div class="live"><span class="dot"></span>Live aggregate surveillance</div>
        <div class="support-pill" title="SOL: 3pLheGVtmHLe5xDpVXWLLPmcKquNLTGMEmzTofxLmoCC">
          <strong>Support:</strong>
          SOL 3pLheGVtmHLe5xDpVXWLLPmcKquNLTGMEmzTofxLmoCC
        </div>
      </div>
    </div>

    <section class="live-market">
      <div class="live-market-header">
        <div class="live-pill"><span class="live-pill-dot"></span>LIVE</div>
      </div>
      <div class="odds-row">
        <div class="odds-main"><span id="poly-odds">--%</span> CHANCE OF PANDEMIC</div>
        <div class="odds-sub" id="poly-side">Hantavirus market probability (YES)</div>
      </div>
      <div class="odds-meta" id="poly-meta">Fetching latest odds...</div>
      <div class="odds-meta">
        Source:
        <a class="odds-link" href="https://polymarket.com/event/hantavirus-pandemic-in-2026" target="_blank" rel="noopener noreferrer">polymarket.com</a>
      </div>
    </section>

    <div class="grid">
      <div class="card fatal-card">
        <div class="fatal-top">
          <div class="label">Fatalities</div>
        </div>
        <div class="fatal-chip"><span class="fatal-skull">☠</span> MONITORED</div>
        <div class="value fatal-value" id="deceased">0</div>
        <div class="sub">Reported death events on map</div>
      </div>
    </div>

    <section class="timeline-panel">
      <div class="timeline-head">
        <span>Timeline Filter</span>
        <span class="timeline-date" id="timeline-date-label">All dates</span>
      </div>
      <input id="timeline-slider" class="timeline-input" type="range" min="0" max="0" value="0" step="1" />
      <div class="timeline-meta" id="timeline-meta">Showing 0 events</div>
    </section>

    <div class="panels">
      <section class="panel">
        <h2>Global Case Map</h2>
        <div id="map"></div>
        <div class="legend">
          <span><i style="background:#ff5b6b"></i>Deaths (skull marker)</span>
          <span><i style="background:#ff3e53"></i>Confirmed case event</span>
          <span><i style="background:#ffc93c"></i>Suspected / quarantine event</span>
          <span>Click markers for timeline details</span>
        </div>
      </section>

      <section class="panel">
        <h2>Live Hantavirus News</h2>
        <div id="news-list" class="news-list">
          <div class="news-state">Loading latest headlines...</div>
        </div>
      </section>

    </div>
  </div>

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    function createIncidentPopup(event) {
      const date = event.date || 'Unknown date';
      return `
        <div class="popup-title">${event.title}</div>
        <div class="popup-row">Type: ${event.type}</div>
        <div class="popup-row">Location: ${event.location}</div>
        <div class="popup-row">Date: ${date}</div>
        <div class="popup-row">${event.details}</div>
        <div class="popup-row">Source: ${event.source}</div>
      `;
    }

    async function loadPolymarketOdds() {
      const oddsEl = document.getElementById('poly-odds');
      const sideEl = document.getElementById('poly-side');
      const metaEl = document.getElementById('poly-meta');
      try {
        const response = await fetch('/api/polymarket');
        const payload = await response.json();
        if (typeof payload.odds_yes_pct === 'number') {
          oddsEl.textContent = `${payload.odds_yes_pct.toFixed(1)}%`;
          sideEl.textContent = 'Hantavirus market probability (YES)';
          const when = payload.fetched_at ? new Date(payload.fetched_at).toLocaleTimeString() : 'unknown';
          metaEl.textContent = `Updated ${when} • refreshes every 2 minutes`;
        } else {
          oddsEl.textContent = '--%';
          sideEl.textContent = 'Hantavirus market probability unavailable';
          metaEl.textContent = payload.error || 'Unable to fetch odds right now.';
        }
      } catch (err) {
        oddsEl.textContent = '--%';
        sideEl.textContent = 'Hantavirus market probability unavailable';
        metaEl.textContent = 'Connection issue while loading Polymarket data.';
      }
    }

    function formatNewsTime(value) {
      if (!value) return 'Unknown time';
      const dt = new Date(value);
      if (Number.isNaN(dt.getTime())) return value;
      return dt.toLocaleString();
    }

    async function loadNews() {
      const listEl = document.getElementById('news-list');
      try {
        const response = await fetch('/api/news');
        const payload = await response.json();
        const items = (payload.items || []).slice().sort((a, b) => {
          const ta = Date.parse(a.published || '');
          const tb = Date.parse(b.published || '');
          const na = Number.isNaN(ta) ? -1 : ta;
          const nb = Number.isNaN(tb) ? -1 : tb;
          return nb - na;
        });
        if (!items.length) {
          listEl.innerHTML = '<div class="news-state">No headlines available right now.</div>';
          return;
        }
        listEl.innerHTML = '';
        items.forEach((item) => {
          const node = document.createElement('article');
          node.className = 'news-item';
          const sourcePart = item.source ? `<span>${item.source}</span>` : '';
          const timePart = item.published ? `<span>${formatNewsTime(item.published)}</span>` : '';
          const metaHtml = (sourcePart || timePart) ? `<div class="news-meta">${sourcePart}${timePart}</div>` : '';
          node.innerHTML = `
            <a href="${item.link}" target="_blank" rel="noopener noreferrer">${item.title}</a>
            ${metaHtml}
          `;
          listEl.appendChild(node);
        });
      } catch (err) {
        listEl.innerHTML = '<div class="news-state">Unable to load live news feed.</div>';
      }
    }

    async function load() {
      await loadPolymarketOdds();
      await loadNews();
      const response = await fetch('/api/cases');
      const payload = await response.json();
      const incidents = payload.incidents || [];
      const slider = document.getElementById('timeline-slider');
      const dateLabel = document.getElementById('timeline-date-label');
      const timelineMeta = document.getElementById('timeline-meta');
      const map = L.map('map', {
        worldCopyJump: false,
        minZoom: 2,
        zoomControl: true,
        maxBounds: [[-85, -540], [85, 540]],
        maxBoundsViscosity: 1.0,
        // Smooth zoom behavior.
        zoomAnimation: true,
        fadeAnimation: true,
        markerZoomAnimation: true,
        zoomSnap: 0.1,
        zoomDelta: 0.5,
        wheelPxPerZoomLevel: 140
      }).setView([8, -20], 2.4);

      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
        subdomains: 'abcd',
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
      }).addTo(map);

      // Keep view inside a 3-world horizontal strip and valid latitudes.
      map.on('drag', () => {
        map.panInsideBounds([[-85, -540], [85, 540]], { animate: false });
      });

      const totals = incidents.reduce((acc, event) => {
        if (event.type === 'death') acc.deceased += 1;
        return acc;
      }, { deceased: 0 });

      document.getElementById('deceased').textContent = totals.deceased.toLocaleString();

      const allDates = Array.from(new Set(
        incidents.map((event) => event.date).filter((date) => Boolean(date))
      )).sort();

      const maxDateIndex = Math.max(allDates.length - 1, 0);
      const sliderResolution = 120; // Higher = smoother drag feel.
      slider.min = "0";
      slider.max = String(Math.max(maxDateIndex * sliderResolution, 1));
      slider.step = "1";
      slider.value = String(maxDateIndex * sliderResolution);

      const renderedMarkers = incidents.map((event) => {
        let marker;
        if (event.type === 'death') {
          const icon = L.divIcon({
            className: '',
            html: '<div class="incident-skull">☠</div>',
            iconSize: [20, 20],
            iconAnchor: [10, 10],
          });
          marker = L.marker([event.lat, event.lon], { icon });
        } else {
          const markerClass = event.type === 'confirmed' ? 'confirmed' : 'suspected';
          const icon = L.divIcon({
            className: '',
            html: `<div class="incident-dot ${markerClass}"></div>`,
            iconSize: [14, 14],
            iconAnchor: [7, 7],
          });
          marker = L.marker([event.lat, event.lon], { icon });
        }
        marker.bindPopup(createIncidentPopup(event));
        return { event, marker };
      });

      function applyTimeline(dateIdx) {
        const cutoffDate = allDates[dateIdx] || allDates[allDates.length - 1] || null;
        let visibleCount = 0;
        renderedMarkers.forEach(({ event, marker }) => {
          const visible = !cutoffDate || !event.date || event.date <= cutoffDate;
          if (visible) {
            marker.addTo(map);
            visibleCount += 1;
          } else {
            map.removeLayer(marker);
          }
        });

        if (cutoffDate) {
          dateLabel.textContent = new Date(`${cutoffDate}T00:00:00Z`).toLocaleDateString();
        } else {
          dateLabel.textContent = 'All dates';
        }
        timelineMeta.textContent = `Showing ${visibleCount} events`;
      }

      function sliderValueToDateIndex(rawValue) {
        if (!allDates.length) return 0;
        const normalized = rawValue / sliderResolution;
        return Math.max(0, Math.min(maxDateIndex, Math.round(normalized)));
      }

      let rafId = null;
      slider.addEventListener('input', (evt) => {
        const nextValue = sliderValueToDateIndex(Number(evt.target.value));
        if (rafId !== null) {
          cancelAnimationFrame(rafId);
        }
        rafId = requestAnimationFrame(() => {
          applyTimeline(nextValue);
          rafId = null;
        });
      });
      applyTimeline(sliderValueToDateIndex(Number(slider.value)));
    }

    load().catch((err) => {
      console.error(err);
      document.body.insertAdjacentHTML('beforeend', '<div style="padding:16px;color:#ffb4bc">Failed to load dashboard data.</div>');
    });
    setInterval(loadPolymarketOdds, 120000);
    setInterval(loadNews, 120000);
  </script>
</body>
</html>
"""


def _fetch_polymarket_yes_odds() -> dict:
    now = time.time()
    fetched_at = POLYMARKET_CACHE.get("fetched_at")
    if fetched_at is not None and now - fetched_at < POLYMARKET_REFRESH_SECONDS:
        cache_age = round(now - fetched_at, 1)
        return {
            "odds_yes_pct": POLYMARKET_CACHE.get("odds_yes_pct"),
            "fetched_at": datetime.fromtimestamp(fetched_at, tz=timezone.utc).isoformat(),
            "cache_age_seconds": cache_age,
            "error": POLYMARKET_CACHE.get("error"),
            "source": POLYMARKET_URL,
        }

    req = urllib.request.Request(
        POLYMARKET_URL,
        headers={
            "User-Agent": POLYMARKET_UA,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    odds_yes_pct = None
    error = None
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        match = re.search(r"(\d+(?:\.\d+)?)%\s*chance", html, flags=re.IGNORECASE)
        if match:
            odds_yes_pct = float(match.group(1))
        else:
            error = "Odds text pattern not found on source page."
    except Exception as exc:  # noqa: BLE001
        error = f"Fetch failed: {exc}"

    POLYMARKET_CACHE["odds_yes_pct"] = odds_yes_pct
    POLYMARKET_CACHE["fetched_at"] = now
    POLYMARKET_CACHE["error"] = error
    POLYMARKET_CACHE["cache_age_seconds"] = 0.0

    return {
        "odds_yes_pct": odds_yes_pct,
        "fetched_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "cache_age_seconds": 0.0,
        "error": error,
        "source": POLYMARKET_URL,
    }


def _fetch_live_news() -> dict:
    now = time.time()
    fetched_at = NEWS_CACHE.get("fetched_at")
    if fetched_at is not None and now - fetched_at < NEWS_REFRESH_SECONDS:
        return {
            "items": NEWS_CACHE.get("items", []),
            "fetched_at": datetime.fromtimestamp(fetched_at, tz=timezone.utc).isoformat(),
            "error": NEWS_CACHE.get("error"),
            "source": NEWS_FEED_URL,
        }

    items = []
    error = None
    req = urllib.request.Request(
        NEWS_FEED_URL,
        headers={
            "User-Agent": POLYMARKET_UA,
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            xml_body = resp.read()
        root = ET.fromstring(xml_body)
        for item in root.findall("./channel/item")[:25]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            source = ""
            source_node = item.find("{http://search.yahoo.com/mrss/}source")
            if source_node is not None and source_node.text:
                source = source_node.text.strip()
            if title and link:
                items.append(
                    {
                        "title": title,
                        "link": link,
                        "published": pub_date,
                        "source": source,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        error = f"News fetch failed: {exc}"

    NEWS_CACHE["items"] = items
    NEWS_CACHE["fetched_at"] = now
    NEWS_CACHE["error"] = error

    return {
        "items": items,
        "fetched_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        "error": error,
        "source": NEWS_FEED_URL,
    }


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path

        if path in ("/", "/index.html"):
            html = _build_html().encode("utf-8")
            self._send(200, html, "text/html; charset=utf-8")
            return

        if path == "/assets/trackhanta-logo-white.png":
            if not LOGO_PATH.is_file():
                self._send(404, b"Logo not found", "text/plain; charset=utf-8")
                return
            data = LOGO_PATH.read_bytes()
            self._send(200, data, "image/png")
            return

        if path == "/favicon.png":
            if not FAVICON_PNG_PATH.is_file():
                self._send(404, b"PNG favicon not found", "text/plain; charset=utf-8")
                return
            data = FAVICON_PNG_PATH.read_bytes()
            self._send(200, data, "image/png")
            return

        if path == "/favicon.ico":
            if not FAVICON_PATH.is_file():
                self._send(404, b"Favicon not found", "text/plain; charset=utf-8")
                return
            data = FAVICON_PATH.read_bytes()
            self._send(200, data, "image/x-icon")
            return

        if path == "/favicon-dark.png":
            if not FAVICON_DARK_PNG_PATH.is_file():
                self._send(404, b"Dark PNG favicon not found", "text/plain; charset=utf-8")
                return
            data = FAVICON_DARK_PNG_PATH.read_bytes()
            self._send(200, data, "image/png")
            return

        if path == "/favicon-dark.ico":
            if not FAVICON_DARK_PATH.is_file():
                self._send(404, b"Dark favicon not found", "text/plain; charset=utf-8")
                return
            data = FAVICON_DARK_PATH.read_bytes()
            self._send(200, data, "image/x-icon")
            return

        if path == "/api/cases":
            payload = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "cases": CASES,
                "incidents": INCIDENTS,
            }
            data = json.dumps(payload).encode("utf-8")
            self._send(200, data, "application/json; charset=utf-8")
            return

        if path == "/api/polymarket":
            payload = _fetch_polymarket_yes_odds()
            data = json.dumps(payload).encode("utf-8")
            self._send(200, data, "application/json; charset=utf-8")
            return

        if path == "/api/news":
            payload = _fetch_live_news()
            data = json.dumps(payload).encode("utf-8")
            self._send(200, data, "application/json; charset=utf-8")
            return

        self._send(404, b"Not found", "text/plain; charset=utf-8")


def main() -> None:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://127.0.0.1:{PORT}/"
        print(f"Track Hanta aggregate dashboard running on {url}")
        print("Press Ctrl+C to stop.")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
