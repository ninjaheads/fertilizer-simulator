from dotenv import load_dotenv
import os
load_dotenv()  # .envから環境変数をロード
import debugpy
debugpy.listen(("0.0.0.0", 5678))
print("✅ debugpy: VSCodeからのアタッチを待っています")
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from supabase_client import supabase
from starlette.middleware.sessions import SessionMiddleware
from collections import defaultdict
from starlette.middleware.sessions import SessionMiddleware
import json

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError("SECRET_KEY is not set in .env")
app.add_middleware(SessionMiddleware, secret_key=secret_key)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/simulate", response_class=HTMLResponse)
async def show_simulate_page(request: Request):
    fertilizers = supabase.table("fertilizers").select("id, brand").execute().data
    return templates.TemplateResponse("simulate.html", {
        "request": request,
        "fertilizers": fertilizers
    })

@app.post("/simulate", response_class=HTMLResponse)
async def simulate(request: Request):
    form = await request.form()
    fertilizer_ids = form.getlist("fertilizers")
    volume_A = float(form.get("volume_A", 0))
    volume_B = float(form.get("volume_B", 0))

    user_inputs = []
    for fid in fertilizer_ids:
        pump = form.get(f"pump_{fid}", "")
        if pump == "原水":
            pump = "Water"

        weight_raw = form.get(f"weight_{fid}")

        if pump == "Water":
            weight = 1.0
            volume = 1.0
        else:
            weight = float(weight_raw) if weight_raw not in [None, ""] else 0.0
            volume = volume_A if pump == "A" else volume_B if pump == "B" else 0.0

        user_inputs.append({
            "id": fid,
            "pump": pump,
            "weight": weight,
            "volume": volume
        })

    response = supabase.table("fertilizer_components").select("fertilizer_id, expressed_as, value").execute()
    components = response.data

    ion_data = supabase.table("ion_conversion").select("expressed_as, ion_form, molar_mass_expressed, molar_mass_ion, ion_count, ion_valence, ion_conductivity").execute().data

    id_to_brand = {
        item["id"]: item["brand"]
        for item in supabase.table("fertilizers").select("id, brand").execute().data
    }

    ordered_elements = [
        "TN", "NN", "AN", "P2O5", "K2O", "CaO", "MgO", "SO3",
        "MnO", "B2O3", "Fe", "Cu", "Zn", "Mo", "NaClO"
    ]

    ordered_ions = [
        "NO3-", "NH4+", "H2PO4-", "HPO4^2-", "PO4^3-",
        "K+", "Ca^2+", "Mg^2+", "SO4^2-", "Cl-"
    ]

    rows = []
    ion_rows = []
    tank_totals = {
        "A": {elem: 0.0 for elem in ordered_elements},
        "B": {elem: 0.0 for elem in ordered_elements},
        "Water": {elem: 0.0 for elem in ordered_elements}
    }

    for item in user_inputs:
        fid = int(item["id"])
        pump = item["pump"]
        weight = item["weight"]
        volume = item["volume"]

        row = {
            "brand": id_to_brand.get(fid, f"ID:{fid}"),
            "pump": pump,
            "weight": weight
        }
        ion_row = {"brand": row["brand"]}

        for elem in ordered_elements:
            row[elem] = ""
        for ion in ordered_ions:
            ion_row[ion] = 0.0

        for comp in components:
            if comp["fertilizer_id"] == fid:
                elem = comp["expressed_as"]
                if elem in ordered_elements and volume > 0:
                    rate = float(comp["value"])
                    ppm = weight * rate * 1_000_000 / volume
                    row[elem] = round(ppm, 2)
                    tank_totals[pump][elem] += ppm

        for conv in ion_data:
            if conv["expressed_as"] in ordered_elements and conv["ion_form"] in ordered_ions:
                if conv["expressed_as"] in row and isinstance(row[conv["expressed_as"]], float):
                    mol_weight = float(conv["molar_mass_expressed"])
                    valence = float(conv["ion_valence"])
                    count = float(conv["ion_count"])
                    ion = conv["ion_form"]
                    ppm = row[conv["expressed_as"]]
                    meq = ppm / mol_weight * count * abs(valence) if mol_weight else 0
                    ion_row[ion] += meq

        ion_row = {k: round(v, 2) if isinstance(v, float) else v for k, v in ion_row.items()}
        rows.append(row)
        ion_rows.append(ion_row)

    ion_elements = ordered_ions
    ion_totals = {
        "A": {ion: 0.0 for ion in ion_elements},
        "B": {ion: 0.0 for ion in ion_elements},
        "Water": {ion: 0.0 for ion in ion_elements}
    }

    for pump in ["A", "B", "Water"]:
        for comp in ion_data:
            expressed = comp["expressed_as"]
            ion = comp["ion_form"]
            if ion not in ion_elements:
                continue
            mol_weight = float(comp["molar_mass_expressed"])
            valence = float(comp["ion_valence"])
            count = float(comp["ion_count"])
            ppm = tank_totals[pump].get(expressed, 0.0)
            meq = ppm / mol_weight * count * abs(valence) if mol_weight else 0
            ion_totals[pump][ion] += meq
    
    ec_results = {}
    for tank in ["A", "B", "Water"]:
        total_ec = 0
        ec_details = {}

        for ion in ordered_ions:
            meq = ion_totals.get(tank, {}).get(ion, 0.0)
            ion_match = next((item for item in ion_data if item["ion_form"] == ion), None)
            conductivity = float(ion_match["ion_conductivity"]) if ion_match else 0.0
            ec = meq * conductivity / 1000
            ec_details[ion] = round(ec, 3)
            total_ec += ec

        ec_results[tank] = {
            "ions": ec_details,
            "total": round(total_ec, 3)
        }

    # ★★★ ここを修正！TemplateResponseを作成してからset_cookie()する！★★★
    context = {
        "request": request,
        "fertilizers": [],
        "rows": rows,
        "elements": ordered_elements,
        "tank_totals": tank_totals,
        "ion_totals": ion_totals,
        "ion_elements": ion_elements,
        "ion_rows": ion_rows,
        "ec_results": ec_results,
    }
    response = templates.TemplateResponse("simulate.html", context)

    # ここでCookieに保存
    response.set_cookie(key="ion_totals", value=json.dumps(ion_totals))
    response.set_cookie(key="ion_conversion", value=json.dumps(ion_data))
    response.set_cookie(key="tank_totals", value=json.dumps(tank_totals))

    # 必要なら有効期限やセキュア属性も付けられる
    # response.set_cookie(key="ion_totals", value=json.dumps(ion_totals), max_age=1800, secure=True)

    return response

@app.get("/fertilizers", response_class=HTMLResponse)
async def list_fertilizers(request: Request):
    response = supabase.table("fertilizers").select("id, brand").execute()
    fertilizers = response.data
    return templates.TemplateResponse("fertilizers.html", {
        "request": request,
        "fertilizers": fertilizers
    })

@app.post("/simulate_ec", response_class=HTMLResponse)
async def simulate_ec(request: Request):
    form = await request.form()
    volume_A = float(form.get("a_volume", 0))
    volume_B = float(form.get("b_volume", 0))
    water_volume = float(form.get("dilution_volume", 0))
    water_pH = float(form.get("dilution_ph", 7))

    # --- データ復元 ---
    original_ion_totals = json.loads(request.cookies.get("ion_totals", "{}"))
    ion_conversion = json.loads(request.cookies.get("ion_conversion", "[]"))
    tank_totals = json.loads(request.cookies.get("tank_totals", "{}"))

    ordered_ions = [
        "NO3-", "NH4+", "H2PO4-", "HPO4^2-", "PO4^3-",
        "K+", "Ca^2+", "Mg^2+", "SO4^2-", "Cl-"
    ]
    trace_keys = ["Mn", "B", "Fe", "Cu", "Zn", "Mo"]

    # --- pH補正 ---
    rounded_pH = round(water_pH, 1)
    response = supabase.table("phosphate_dissociation").select("*").eq("pH", rounded_pH).execute()
    if not response.data:
        raise ValueError(f"No phosphate dissociation data found for pH = {rounded_pH}")

    row = response.data[0]
    phosphate_ratios = {k: float(row.get(k, 0)) for k in ["H2PO4-", "HPO4^2-", "PO4^3-"]}

    corrected_ion_totals = {}
    for tank, ion_dict in original_ion_totals.items():
        corrected_ion_totals[tank] = {
            ion: (val * phosphate_ratios[ion] if ion in phosphate_ratios else val)
            for ion, val in ion_dict.items()
        }

    # --- 微量要素計算 ---
    element_conversion = supabase.table("element_conversion").select("*").execute().data
    conv_dict = {row["oxide_name"]: {"symbol": row["element_symbol"], "rate": row["element_mw"]/row["oxide_mw"]} for row in element_conversion}

    trace_totals = {tank: {} for tank in tank_totals}
    for tank, elem_dict in tank_totals.items():
        for elem, ppm in elem_dict.items():
            if elem in conv_dict:
                symbol = conv_dict[elem]["symbol"]
                rate = conv_dict[elem]["rate"]
                trace_totals[tank][symbol] = round(ppm * rate, 3)
            elif elem in trace_keys:
                trace_totals[tank][elem] = round(ppm, 3)

    # --- unified_rows作成 ---
    tanks = ["A", "B", "Water"]
    tank_volumes = {"A": volume_A, "B": volume_B, "Water": water_volume}
    unified_rows = []
    for tank in tanks:
        row = {"tank": tank}
        for ion in ordered_ions:
            row[ion] = round(corrected_ion_totals[tank][ion] * tank_volumes[tank], 3)
        for elem in trace_keys:
            row[elem] = round(trace_totals[tank].get(elem, 0) * tank_volumes[tank], 3)
        unified_rows.append(row)
    # 合計行
    total_row = {"tank": "Total"}
    for key in ordered_ions + trace_keys:
        total_row[key] = round(sum(row[key] for row in unified_rows), 3)
    unified_rows.append(total_row)

    # --- 1Lあたり行とEC ---
    total_volume = volume_A + volume_B + water_volume
    one_liter_me = {}
    for key in ordered_ions + trace_keys:
        one_liter_me[key] = round(total_row[key] / total_volume, 3) if total_volume > 0 else 0.0

    ec_by_ion = {}
    ec_total = 0.0
    for ion in ordered_ions:
        conductivity = 0.0
        for conv in ion_conversion:
            if conv["ion_form"] == ion:
                conductivity = float(conv["ion_conductivity"])
                break
        ec_val = one_liter_me[ion] * conductivity / 1000
        ec_by_ion[ion] = round(ec_val, 3)
        ec_total += ec_val
    ec_total = round(ec_total, 3)

    context = {
        "request": request,
        "volume_A": volume_A,
        "volume_B": volume_B,
        "water_volume": water_volume,
        "water_pH": water_pH,
        "unified_rows": unified_rows,
        "ion_keys": ordered_ions,
        "trace_keys": trace_keys,
        "one_liter_me": one_liter_me,
        "ec_by_ion": ec_by_ion,
        "ec_total": ec_total
    }

    return templates.TemplateResponse("simulate_ec.html", context)
