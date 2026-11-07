"""
FCi asset prep (Blender 4.0+, headless):  blender -b -P prep_assets.py
1. Pulls the textures out of selected BlenderKit materials on this PC, works out what each map is
   (base colour / roughness / normal / alpha) and saves web-sized JPGs to site/tex/<key>/<role>.jpg
   plus 256px previews to assets/probe/ so they can be reviewed.
2. Renders a physically based sunset sky (Cycles + Nishita) to site/env/dusk.hdr for reflections/background.
Writes assets/probe/report.json.
"""
import bpy, os, json, glob, math, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
BK = os.path.join(os.path.expanduser("~"), "blenderkit_data", "materials")
TEX = os.path.join(HERE, "site", "tex"); ENV = os.path.join(HERE, "site", "env"); PROBE = os.path.join(HERE, "assets", "probe")
for d in (TEX, ENV, PROBE): os.makedirs(d, exist_ok=True)
T0 = time.time()

CANDIDATES = {   # key: folder-name prefix inside blenderkit_data/materials
  "concrete":     "concrete_f230eca5",
  "concrete_dots":"gray-concrete-wi",
  "stone_tiles":  "stone-tiles",
  "stone_floor":  "stone-floor",
  "stucco":       "stucco-wall-v8",
  "wall_pale":    "wall-pale",
  "steel":        "stainless-steel",
  "vents":        "metal-vents",
  "pavers":       "zigzag-unipaver-",
  "wood_white":   "wood-white",
  "leaves_green": "leaves_green",
  "leaf":         "leaf-1",
  "forest_leaves":"forest_leaves_02",
  "bark":         "tree-bark_1d8703fc",
  "bark2":        "pbr-bark",
}

def role_of(node):
    """Follow links from an image node to the Principled input it ends up driving."""
    seen = set(); stack = [(node, None)]
    while stack:
        n, via = stack.pop()
        if n.name in seen: continue
        seen.add(n.name)
        for out in n.outputs:
            for l in out.links:
                t = l.to_node
                if t.type == 'BSDF_PRINCIPLED':
                    name = l.to_socket.name
                    if out.name == "Alpha" or name == "Alpha": return "alpha"
                    return {"Base Color": "color", "Roughness": "rough", "Metallic": "metal", "Normal": "normal",
                            "Emission Color": "emit", "Alpha": "alpha"}.get(name, name.lower().replace(" ", "_"))
                if t.type == 'NORMAL_MAP': return "normal"
                if t.type in ('BUMP', 'DISPLACEMENT'): return "height"
                if t.type == 'OUTPUT_MATERIAL': return "disp"
                stack.append((t, l))
    return None

report = {}
for key, prefix in CANDIDATES.items():
    entry = {"blend": None, "maps": {}, "error": None}
    try:
        dirs = sorted(glob.glob(os.path.join(BK, prefix + "*")))
        blends = sorted(glob.glob(os.path.join(dirs[0], "*.blend"))) if dirs else []
        if not blends: entry["error"] = "not found"; report[key] = entry; continue
        entry["blend"] = os.path.basename(blends[0])
        before = set(bpy.data.materials)
        with bpy.data.libraries.load(blends[0], link=False) as (src, dst):
            dst.materials = list(src.materials)
        mats = [m for m in bpy.data.materials if m not in before and m.use_nodes]
        os.makedirs(os.path.join(TEX, key), exist_ok=True)
        for m in mats:
            for n in m.node_tree.nodes:
                if n.type != 'TEX_IMAGE' or not n.image: continue
                img = n.image; role = role_of(n) or "unknown"
                if role in entry["maps"]: continue
                w, h = img.size
                if w == 0: continue
                has_alpha = bool(img.alpha_mode != 'NONE' and img.channels == 4 and img.depth in (32, 64, 128))
                for size, folder, fname in ((1024, os.path.join(TEX, key), role + ".jpg"), (256, PROBE, key + "__" + role + ".jpg")):
                    c = img.copy(); s = min(1.0, size / max(w, h)); c.scale(max(1, int(w * s)), max(1, int(h * s)))
                    c.filepath_raw = os.path.join(folder, fname); c.file_format = 'JPEG'; c.save()
                    if role == "color" and has_alpha and size == 1024:
                        c.filepath_raw = os.path.join(folder, "color_alpha.png"); c.file_format = 'PNG'; c.save()
                    bpy.data.images.remove(c)
                entry["maps"][role] = {"image": img.name, "size": [w, h], "colorspace": img.colorspace_settings.name,
                                       "alpha": has_alpha, "material": m.name,
                                       "mapping_scale": None}
                # texture scale if a Mapping node feeds this image
                for l in n.inputs["Vector"].links if "Vector" in n.inputs else []:
                    if l.from_node.type == 'MAPPING':
                        entry["maps"][role]["mapping_scale"] = list(l.from_node.inputs["Scale"].default_value)
    except Exception as e:
        entry["error"] = repr(e) + " " + traceback.format_exc()[-400:]
    report[key] = entry
    print("PROBE", key, list(entry["maps"].keys()), entry["error"])

# ---------------------------------------------------------------- sunset sky HDR (Cycles, Nishita)
sky = {"ok": False}
try:
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    try: scene.cycles.device = 'CPU'
    except Exception: pass
    world = bpy.data.worlds.new("Dusk"); scene.world = world; world.use_nodes = True
    nt = world.node_tree; bg = nt.nodes["Background"]
    skyn = nt.nodes.new("ShaderNodeTexSky"); skyn.sky_type = 'NISHITA'
    skyn.sun_elevation = math.radians(3.5); skyn.sun_rotation = math.radians(60)
    skyn.altitude = 120; skyn.air_density = 1.2; skyn.dust_density = 3.0; skyn.ozone_density = 1.0
    skyn.sun_size = math.radians(1.2); skyn.sun_intensity = 0.6
    nt.links.new(skyn.outputs["Color"], bg.inputs["Color"]); bg.inputs["Strength"].default_value = 0.35
    for ob in list(scene.objects): bpy.data.objects.remove(ob)
    cd = bpy.data.cameras.new("Pano"); cd.type = 'PANO'
    try: cd.panorama_type = 'EQUIRECTANGULAR'
    except Exception: cd.cycles.panorama_type = 'EQUIRECTANGULAR'
    cam = bpy.data.objects.new("Pano", cd); cam.rotation_euler = (math.radians(90), 0, 0)
    scene.collection.objects.link(cam); scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 2048, 1024
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'Standard'
    scene.render.image_settings.file_format = 'HDR'
    scene.render.filepath = os.path.join(ENV, "dusk.hdr")
    bpy.ops.render.render(write_still=True)
    scene.render.image_settings.file_format = 'JPEG'
    scene.view_settings.view_transform = 'AgX' if 'AgX' in [i.identifier for i in scene.view_settings.bl_rna.properties['view_transform'].enum_items] else 'Filmic'
    scene.render.resolution_x, scene.render.resolution_y = 1024, 512
    scene.render.filepath = os.path.join(PROBE, "sky_preview.jpg")
    bpy.ops.render.render(write_still=True)
    sky = {"ok": True, "elevation_deg": 3.5, "rotation_deg": 60, "file": "site/env/dusk.hdr"}
except Exception as e:
    sky = {"ok": False, "error": repr(e) + " " + traceback.format_exc()[-400:]}

report["_sky"] = sky
report["_time_s"] = round(time.time() - T0)
with open(os.path.join(PROBE, "report.json"), "w") as fh: json.dump(report, fh, indent=1)
print("FCI_PREP_OK", report["_time_s"], "s")
