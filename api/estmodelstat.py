from copy import deepcopy
from csv import DictWriter
from estmodel import find, run


def find_subcatchments(object):
    subcatchments = [object] if "year" not in object else []
    for sc in object["subcatchments"]:
        subcatchments.extend(find_subcatchments(sc))
    return subcatchments


def sumattr(object, name, parameter=None):
    result = 0.0
    if name in object:
        return object[name]
    elif "year" in object:
        for sc in find_subcatchments(object):
            result += sumattr(sc, name, parameter)
    elif name == "discharge":
        for m in object["measurements"]:
            if m["parameter"] == parameter:
                result += m[name]
    elif name == "factor":
        for a in object["adjustments"]:
            if a["parameter"] == parameter:
                result *= a[name]
    elif "subcatchments" in object:
        for ds in object["diffuseSources"]:
            result += sumattr(ds, name, parameter)
        for ps in object["pointSources"]:
            result += sumattr(ps, name, parameter)
    elif name in ["anthropogenicDischarge", "atmosphericDeposition", "naturalDischarge", "retention"]:
        for e in object["estimates"]:
            if e["parameter"] == parameter:
                result += e[name]
    elif name == "amount":
        for f in object.get("fertilizers", []):
            if f["parameter"] == parameter:
                result += f[name]
    return result


models = []
for station in find("stations", type="hydrochemical"):
    models.extend(find("stations", station["code"], "models"))
for waterbody in find("waterbodies"):
    models.extend(find("waterbodies", waterbody["code"], "models"))

rows = []
for model in models:
    print(model["code"], model["name"])
    model2 = deepcopy(model)
    for sc in find_subcatchments(model2):
        sc["adjustments"] = []
        sc["measurements"] = []
    model2 = run(model2)
    rows.append({
        "year": model["year"],
        "type": "catchment",
        "c_code": model["code"],
        "c_name": model["name"],
        "area": sumattr(model, "area"),
        "flow_q": sum(sc["waterDischarge"] for sc in model["subcatchments"]),
        "drained_area": sumattr(model, "drainedArea"),
        "harvested_area": sumattr(model, "harvestedArea"),
        "clay_soil_area": sumattr(model, "claySoilArea"),
        "fertile_soil_area": sumattr(model, "fertileSoilArea"),
        "peat_soil_area": sumattr(model, "peatSoilArea"),
        "scattered_population": sumattr(model, "scatteredPopulation"),
        "tn_fertilizer_amount": sumattr(model, "amount", "tn"),
        "tp_fertilizer_amount": sumattr(model, "amount", "tp"),
        "tn_anthropogenic_unadjusted_estimate": sumattr(model2, "anthropogenicDischarge", "tn"),
        "tn_atmospheric_unadjusted_estimate": sumattr(model2, "atmosphericDeposition", "tn"),
        "tn_natural_unadjusted_estimate": sumattr(model2, "naturalDischarge", "tn"),
        "tn_unadjusted_retention": sumattr(model2, "retention", "tn"),
        "tn_anthropogenic_estimate": sumattr(model, "anthropogenicDischarge", "tn"),
        "tn_atmospheric_estimate": sumattr(model, "atmosphericDeposition", "tn"),
        "tn_natural_estimate": sumattr(model, "naturalDischarge", "tn"),
        "tn_retention": sumattr(model, "retention", "tn"),
        "tp_anthropogenic_unadjusted_estimate": sumattr(model2, "anthropogenicDischarge", "tp"),
        "tp_atmospheric_unadjusted_estimate": sumattr(model2, "atmosphericDeposition", "tp"),
        "tp_natural_unadjusted_estimate": sumattr(model2, "naturalDischarge", "tp"),
        "tp_unadjusted_retention": sumattr(model2, "retention", "tp"),
        "tp_anthropogenic_estimate": sumattr(model, "anthropogenicDischarge", "tp"),
        "tp_atmospheric_estimate": sumattr(model, "atmosphericDeposition", "tp"),
        "tp_natural_estimate": sumattr(model, "naturalDischarge", "tp"),
        "tp_retention": sumattr(model, "retention", "tp")
    })
    for sc, sc2 in zip(find_subcatchments(model), find_subcatchments(model2)):
        sc_area = sumattr(sc, "area")
        sc_flow_q = (sc["waterDischarge"] - sum(ssc["waterDischarge"]
                     for ssc in sc["subcatchments"]))
        rows.append({
            "year": model["year"],
            "type": "subcatchment",
            "c_code": model["code"],
            "c_name": model["name"],
            "sc_code": sc["code"],
            "sc_name": sc["name"],
            "area": sc_area,
            "distance": sc["distance"],
            "depth": sc["waterDepth"],
            "flow_q": sc_flow_q,
            "flow_v": sc["flowVelocity"],
            "tn_measurement": sumattr(sc, "discharge", "tn") or None,
            "tp_measurement": sumattr(sc, "discharge", "tp") or None,
            "drained_area": sumattr(sc, "drainedArea"),
            "harvested_area": sumattr(sc, "harvestedArea"),
            "clay_soil_area": sumattr(sc, "claySoilArea"),
            "fertile_soil_area": sumattr(sc, "fertileSoilArea"),
            "peat_soil_area": sumattr(sc, "peatSoilArea"),
            "scattered_population": sumattr(sc, "scatteredPopulation"),
            "tn_fertilizer_amount": sumattr(sc, "amount", "tn"),
            "tp_fertilizer_amount": sumattr(sc, "amount", "tp"),
            "tn_anthropogenic_unadjusted_estimate": sumattr(sc2, "anthropogenicDischarge", "tn"),
            "tn_atmospheric_unadjusted_estimate": sumattr(sc2, "atmosphericDeposition", "tn"),
            "tn_natural_unadjusted_estimate": sumattr(sc2, "naturalDischarge", "tn"),
            "tn_unadjusted_retention": sumattr(sc2, "retention", "tn"),
            "tn_anthropogenic_estimate": sumattr(sc, "anthropogenicDischarge", "tn"),
            "tn_atmospheric_estimate": sumattr(sc, "atmosphericDeposition", "tn"),
            "tn_natural_estimate": sumattr(sc, "naturalDischarge", "tn"),
            "tn_retention": sumattr(sc, "retention", "tn"),
            "tp_anthropogenic_unadjusted_estimate": sumattr(sc2, "anthropogenicDischarge", "tp"),
            "tp_atmospheric_unadjusted_estimate": sumattr(sc2, "atmosphericDeposition", "tp"),
            "tp_natural_unadjusted_estimate": sumattr(sc2, "naturalDischarge", "tp"),
            "tp_unadjusted_retention": sumattr(sc2, "retention", "tp"),
            "tp_anthropogenic_estimate": sumattr(sc, "anthropogenicDischarge", "tp"),
            "tp_atmospheric_estimate": sumattr(sc, "atmosphericDeposition", "tp"),
            "tp_natural_estimate": sumattr(sc, "naturalDischarge", "tp"),
            "tp_retention": sumattr(sc, "retention", "tp")
        })
        for ds, ds2 in zip(sc["diffuseSources"], sc2["diffuseSources"]):
            rows.append({
                "year": model["year"],
                "type": ds["type"] or "other",
                "c_code": model["code"],
                "c_name": model["name"],
                "sc_code": sc["code"],
                "sc_name": sc["name"],
                "area": ds["area"],
                "distance": sc["distance"],
                "depth": sc["waterDepth"],
                "flow_q": sc_flow_q / sc_area * ds["area"],
                "flow_v": sc["flowVelocity"],
                "drained_area": ds["drainedArea"],
                "harvested_area": ds["harvestedArea"],
                "clay_soil_area": ds["claySoilArea"],
                "fertile_soil_area": ds["fertileSoilArea"],
                "peat_soil_area": ds["peatSoilArea"],
                "scattered_population": ds["scatteredPopulation"],
                "tn_fertilizer_amount": sumattr(ds, "amount", "tn"),
                "tp_fertilizer_amount": sumattr(ds, "amount", "tp"),
                "tn_anthropogenic_unadjusted_estimate": sumattr(ds2, "anthropogenicDischarge", "tn"),
                "tn_atmospheric_unadjusted_estimate": sumattr(ds2, "atmosphericDeposition", "tn"),
                "tn_natural_unadjusted_estimate": sumattr(ds2, "naturalDischarge", "tn"),
                "tn_unadjusted_retention": sumattr(ds2, "retention", "tn"),
                "tn_anthropogenic_estimate": sumattr(ds, "anthropogenicDischarge", "tn"),
                "tn_atmospheric_estimate": sumattr(ds, "atmosphericDeposition", "tn"),
                "tn_natural_estimate": sumattr(ds, "naturalDischarge", "tn"),
                "tn_retention": sumattr(ds, "retention", "tn"),
                "tp_anthropogenic_unadjusted_estimate": sumattr(ds2, "anthropogenicDischarge", "tp"),
                "tp_atmospheric_unadjusted_estimate": sumattr(ds2, "atmosphericDeposition", "tp"),
                "tp_natural_unadjusted_estimate": sumattr(ds2, "naturalDischarge", "tp"),
                "tp_unadjusted_retention": sumattr(ds2, "retention", "tp"),
                "tp_anthropogenic_estimate": sumattr(ds, "anthropogenicDischarge", "tp"),
                "tp_atmospheric_estimate": sumattr(ds, "atmosphericDeposition", "tp"),
                "tp_natural_estimate": sumattr(ds, "naturalDischarge", "tp"),
                "tp_retention": sumattr(ds, "retention", "tp")
            })
        for ps, ps2 in zip(sc["pointSources"], sc2["pointSources"]):
            rows.append({
                "year": model["year"],
                "type": "point",
                "c_code": model["code"],
                "c_name": model["name"],
                "sc_code": sc["code"],
                "sc_name": sc["name"],
                "s_code": ps["code"],
                "s_name": ps["name"],
                "distance": ps["distance"],
                "depth": sc["waterDepth"],
                "flow_q": ps["waterDischarge"],
                "flow_v": sc["flowVelocity"],
                "tn_measurement": sumattr(ps, "discharge", "tn") or None,
                "tp_measurement": sumattr(ps, "discharge", "tp") or None,
                "tn_anthropogenic_unadjusted_estimate": sumattr(ps2, "anthropogenicDischarge", "tn"),
                "tn_atmospheric_unadjusted_estimate": sumattr(ps2, "atmosphericDeposition", "tn"),
                "tn_natural_unadjusted_estimate": sumattr(ps2, "naturalDischarge", "tn"),
                "tn_unadjusted_retention": sumattr(ps2, "retention", "tn"),
                "tn_anthropogenic_estimate": sumattr(ps, "anthropogenicDischarge", "tn"),
                "tn_atmospheric_estimate": sumattr(ps, "atmosphericDeposition", "tn"),
                "tn_natural_estimate": sumattr(ps, "naturalDischarge", "tn"),
                "tn_retention": sumattr(ps, "retention", "tn"),
                "tp_anthropogenic_unadjusted_estimate": sumattr(ps2, "anthropogenicDischarge", "tp"),
                "tp_atmospheric_unadjusted_estimate": sumattr(ps2, "atmosphericDeposition", "tp"),
                "tp_natural_unadjusted_estimate": sumattr(ps2, "naturalDischarge", "tp"),
                "tp_unadjusted_retention": sumattr(ps2, "retention", "tp"),
                "tp_anthropogenic_estimate": sumattr(ps, "anthropogenicDischarge", "tp"),
                "tp_atmospheric_estimate": sumattr(ps, "atmosphericDeposition", "tp"),
                "tp_natural_estimate": sumattr(ps, "naturalDischarge", "tp"),
                "tp_retention": sumattr(ps, "retention", "tp")
            })
with open("models.csv", "w", newline="") as file:
    writer = DictWriter(file, delimiter=";", fieldnames=[
        "year",
        "type",
        "c_code",
        "c_name",
        "sc_code",
        "sc_name",
        "s_code",
        "s_name",
        "area",
        "distance",
        "depth",
        "flow_q",
        "flow_v",
        "tn_measurement",
        "tp_measurement",
        "drained_area",
        "harvested_area",
        "clay_soil_area",
        "fertile_soil_area",
        "peat_soil_area",
        "scattered_population",
        "tn_fertilizer_amount",
        "tp_fertilizer_amount",
        "tn_anthropogenic_unadjusted_estimate",
        "tn_atmospheric_unadjusted_estimate",
        "tn_natural_unadjusted_estimate",
        "tn_unadjusted_estimate",
        "tn_unadjusted_retention",
        "tn_adjustment",
        "tn_anthropogenic_estimate",
        "tn_atmospheric_estimate",
        "tn_natural_estimate",
        "tn_estimate",
        "tn_retention",
        "tp_anthropogenic_unadjusted_estimate",
        "tp_atmospheric_unadjusted_estimate",
        "tp_natural_unadjusted_estimate",
        "tp_unadjusted_estimate",
        "tp_unadjusted_retention",
        "tp_adjustment",
        "tp_anthropogenic_estimate",
        "tp_atmospheric_estimate",
        "tp_natural_estimate",
        "tp_estimate",
        "tp_retention"
    ])
    writer.writeheader()
    for row in rows:
        # TN
        row["tn_unadjusted_estimate"] = 0.0
        row["tn_unadjusted_estimate"] += row["tn_anthropogenic_unadjusted_estimate"]
        row["tn_unadjusted_estimate"] += row["tn_natural_unadjusted_estimate"]
        row["tn_estimate"] = 0.0
        row["tn_estimate"] += row["tn_anthropogenic_estimate"]
        row["tn_estimate"] += row["tn_natural_estimate"]
        if row["tn_unadjusted_estimate"]:
            row["tn_adjustment"] = row["tn_estimate"]
            row["tn_adjustment"] /= row["tn_unadjusted_estimate"]
        else:
            row["tn_adjustment"] = 1.0
        row["tn_unadjusted_estimate"] += row["tn_atmospheric_unadjusted_estimate"]
        row["tn_estimate"] += row["tn_atmospheric_estimate"]
        # TP
        row["tp_unadjusted_estimate"] = 0.0
        row["tp_unadjusted_estimate"] += row["tp_anthropogenic_unadjusted_estimate"]
        row["tp_unadjusted_estimate"] += row["tp_natural_unadjusted_estimate"]
        row["tp_estimate"] = 0.0
        row["tp_estimate"] += row["tp_anthropogenic_estimate"]
        row["tp_estimate"] += row["tp_natural_estimate"]
        if row["tp_unadjusted_estimate"]:
            row["tp_adjustment"] = row["tp_estimate"]
            row["tp_adjustment"] /= row["tp_unadjusted_estimate"]
        else:
            row["tp_adjustment"] = 1.0
        row["tp_unadjusted_estimate"] += row["tp_atmospheric_unadjusted_estimate"]
        row["tp_estimate"] += row["tp_atmospheric_estimate"]
    writer.writerows(rows)
