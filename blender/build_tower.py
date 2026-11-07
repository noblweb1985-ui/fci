"""
FCi tower — procedural Blender build (Blender 4.0+)
Run headless:  blender -b -P build_tower.py
Outputs (next to this script):
  fci_tower.blend       editable scene
  fci_tower.glb         web model (one named object per level: P1, L01..L21, Roof, Canopy, Fins, Core, Plaza)
  building.json         level heights + ellipse radii (three.js coords) for the yellow floor outlines
  preview_front.png / preview_entrance.png / preview_parking.png
Units: metres. Blender Z-up, building front faces -Y (becomes +Z in three.js).
"""
import bpy, bmesh, math, os, json, random, sys, time

OUT = os.path.dirname(os.path.abspath(__file__))
random.seed(7)
T0 = time.time()

# ---------------------------------------------------------------- parameters
RX, RY = 17.0, 12.5          # tower ellipse half-width (x) / half-depth (y)
LOBBY_H = 8.0                # double-height lobby
CANOPY_T = 0.9               # podium canopy thickness
FH = 3.2                     # residential floor height
FIRST = 2                    # first residential level number
LAST = 21                    # top residential level
CROWN_FROM = 20              # levels with flared crown slabs
BASE0 = LOBBY_H + CANOPY_T   # z of level 2 floor
def zbase(k): return BASE0 + (k - FIRST) * FH
ROOF_Z = zbase(LAST) + FH
FIN_TOP = zbase(19) + FH
PRX, PRY = 20.5, 15.5        # podium (lobby) glass ellipse
P1_Z0, P1_Z1 = -4.2, -0.4    # parking level
PW, PD = 60.0, 46.0          # parking footprint

# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---------------------------------------------------------------- materials
MATS = {}
TEXDIR = os.path.join(OUT, "assets", "tex512")   # 512px copies keep the web model light
def add_tex(m, key):
    """Hook up colour / roughness / normal maps extracted by prep_assets.py (BlenderKit textures)."""
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    def img(role, noncolor):
        f = os.path.join(TEXDIR, key, role + ".jpg")
        if not os.path.exists(f): return None
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = bpy.data.images.load(f, check_existing=True)
        if noncolor: n.image.colorspace_settings.name = 'Non-Color'
        return n
    c = img("color", False)
    if c: nt.links.new(c.outputs["Color"], b.inputs["Base Color"])
    r = img("rough", True)
    if r: nt.links.new(r.outputs["Color"], b.inputs["Roughness"])
    nm = img("normal", True)
    if nm:
        nmap = nt.nodes.new("ShaderNodeNormalMap"); nmap.inputs["Strength"].default_value = 0.8
        nt.links.new(nm.outputs["Color"], nmap.inputs["Color"]); nt.links.new(nmap.outputs["Normal"], b.inputs["Normal"])
def mat(name, color, rough=0.5, metal=0.0, alpha=1.0, emit=None, emit_strength=0.0, tex=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    def setin(key, val):
        if key in b.inputs: b.inputs[key].default_value = val
    setin("Base Color", (*color, 1))
    setin("Roughness", rough)
    setin("Metallic", metal)
    setin("Alpha", alpha)
    if emit:
        setin("Emission Color", (*emit, 1)); setin("Emission", (*emit, 1))
        setin("Emission Strength", emit_strength)
    if alpha < 1:
        m.blend_method = 'BLEND'
        if hasattr(m, "shadow_method"): m.shadow_method = 'HASHED'
        if hasattr(m, "show_backface"): m.show_backface = False
    m.use_backface_culling = False
    if tex: add_tex(m, tex)
    MATS[name] = m
    return m

def srgb(h):
    h = h.lstrip('#'); c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

mat("White",      srgb("EEEBE5"), 0.45)
mat("Stone",      srgb("E4DFD6"), 0.6)
mat("Glass",      srgb("5A86B8"), 0.03, 0.75, alpha=0.88)
mat("LobbyGlass", srgb("8FA7B8"), 0.03, 0.3, alpha=0.35)
mat("Rail",       srgb("BFD3E0"), 0.03, 0.2, alpha=0.28)
mat("Dark",       srgb("2B2F36"), 0.35, 0.6)
mat("Mullion",    srgb("3A3F47"), 0.4, 0.7)
mat("Room",       srgb("8E96A0"), 0.8, emit=srgb("FFE7C2"), emit_strength=0.05)
mat("RoomLit",    srgb("F2D9AE"), 0.8, emit=srgb("FFD08A"), emit_strength=2.2)
mat("LobbyWarm",  srgb("D9B98A"), 0.6, emit=srgb("FFCF8A"), emit_strength=1.6)
mat("Light",      srgb("FFFFFF"), 0.5, emit=srgb("FFE2B0"), emit_strength=12.0)
mat("Paving",     srgb("BDB6AC"), 0.75)
mat("Steel",      srgb("C9CCD0"), 0.2, 1.0)
mat("Green",      srgb("4C6B32"), 0.9)
mat("Wood",       srgb("8A5A33"), 0.6)
mat("Concrete",   srgb("B9B1A6"), 0.85)
mat("ConcFloor",  srgb("8F8A84"), 0.25)
mat("Yellow",     srgb("F5A81C"), 0.5)            # FCi yellow on the parking columns
mat("Paint",      srgb("F2F2F0"), 0.6)
mat("Red",        srgb("B3261E"), 0.5, 0.2)
mat("CarSilver",  srgb("C8CACC"), 0.25, 0.8)
mat("CarDark",    srgb("23262B"), 0.25, 0.6)
mat("Daylight",   srgb("FFE9C4"), 0.5, emit=srgb("FFE3B5"), emit_strength=5.0)
mat("Tube",       srgb("FFFFFF"), 0.5, emit=srgb("FFF1DC"), emit_strength=8.0)

# ---------------------------------------------------------------- geometry builder
def P(rx, ry, a, z, cx=0.0, cy=0.0):
    r = math.radians(a)
    return (cx + rx * math.sin(r), cy - ry * math.cos(r), z)

class G:
    def __init__(self, name): self.name = name; self.v = []; self.f = []; self.m = []
    def poly(self, pts, mt):
        b = len(self.v); self.v += pts; self.f.append(tuple(range(b, b + len(pts)))); self.m.append(mt)
    def _faces(self, idx_faces, mt):
        for fc in idx_faces: self.f.append(fc); self.m.append(mt)

    def box(self, cx, cy, cz, sx, sy, sz, mt, rotz=0.0):
        c, s = math.cos(rotz), math.sin(rotz); b = len(self.v)
        for dz in (-0.5, 0.5):
            for dx, dy in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5)):
                x, y = dx * sx, dy * sy
                self.v.append((cx + x * c - y * s, cy + x * s + y * c, cz + dz * sz))
        self._faces([(b+3, b+2, b+1, b), (b+4, b+5, b+6, b+7), (b, b+1, b+5, b+4),
                     (b+1, b+2, b+6, b+5), (b+2, b+3, b+7, b+6), (b+3, b, b+4, b+7)], mt)

    def disc(self, rx, ry, z0, z1, n, mt, cx=0.0, cy=0.0):
        b = len(self.v)
        for z in (z0, z1):
            for i in range(n): self.v.append(P(rx, ry, -180 + 360 * i / n, z, cx, cy))
        self._faces([tuple(range(b + n - 1, b - 1, -1)), tuple(range(b + n, b + 2 * n))], mt)
        self._faces([(b + i, b + (i + 1) % n, b + n + (i + 1) % n, b + n + i) for i in range(n)], mt)

    def sector(self, rxi, ryi, rxo, ryo, z0, z1, a0, a1, n, mt):
        full = (a1 - a0) >= 359.99
        A = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
        b = len(self.v)
        for (rx, ry, z) in ((rxi, ryi, z0), (rxo, ryo, z0), (rxi, ryi, z1), (rxo, ryo, z1)):
            for a in A: self.v.append(P(rx, ry, a, z))
        m = n + 1
        ib, ob, it, ot = b, b + m, b + 2 * m, b + 3 * m
        fs = []
        for i in range(n):
            fs += [(it+i, ot+i, ot+i+1, it+i+1), (ib+i+1, ob+i+1, ob+i, ib+i),
                   (ob+i, ob+i+1, ot+i+1, ot+i), (ib+i+1, ib+i, it+i, it+i+1)]
        if not full:
            fs += [(ib, it, ot, ob), (ob+n, ot+n, it+n, ib+n)]
        self._faces(fs, mt)

    def wall(self, rx, ry, z0, z1, a0, a1, n, mt):
        A = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
        b = len(self.v)
        for a in A: self.v.append(P(rx, ry, a, z0))
        for a in A: self.v.append(P(rx, ry, a, z1))
        m = n + 1
        self._faces([(b+i, b+i+1, b+m+i+1, b+m+i) for i in range(n)], mt)

    def torus(self, cx, cy, cz, R, r, mt, nu=40, nv=6):
        b = len(self.v)
        for i in range(nu):
            u = 2 * math.pi * i / nu
            for j in range(nv):
                w = 2 * math.pi * j / nv
                self.v.append((cx + (R + r * math.cos(w)) * math.cos(u), cy + (R + r * math.cos(w)) * math.sin(u), cz + r * math.sin(w)))
        self._faces([(b + i*nv + j, b + ((i+1)%nu)*nv + j, b + ((i+1)%nu)*nv + (j+1)%nv, b + i*nv + (j+1)%nv)
                     for i in range(nu) for j in range(nv)], mt)

    def sphere(self, cx, cy, cz, r, mt, nu=12, nv=7, sz=1.0):
        b = len(self.v)
        self.v.append((cx, cy, cz - r * sz))
        for j in range(1, nv):
            ph = math.pi * j / nv - math.pi / 2
            for i in range(nu):
                t = 2 * math.pi * i / nu
                self.v.append((cx + r * math.cos(ph) * math.cos(t), cy + r * math.cos(ph) * math.sin(t), cz + r * sz * math.sin(ph)))
        top = len(self.v); self.v.append((cx, cy, cz + r * sz))
        fs = [(b, b + 1 + (i+1) % nu, b + 1 + i) for i in range(nu)]
        for j in range(nv - 2):
            r0 = b + 1 + j * nu; r1 = r0 + nu
            fs += [(r0+i, r0+(i+1)%nu, r1+(i+1)%nu, r1+i) for i in range(nu)]
        last = b + 1 + (nv - 2) * nu
        fs += [(last + i, last + (i+1) % nu, top) for i in range(nu)]
        self._faces(fs, mt)

    def build(self, smooth=True):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.v, [], self.f)
        names = sorted(set(self.m), key=lambda s: self.m.index(s))
        for nme in names: me.materials.append(MATS[nme])
        idx = {nme: i for i, nme in enumerate(names)}
        for p, mt in zip(me.polygons, self.m): p.material_index = idx[mt]
        me.validate(); me.update()
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        uvl = bm.loops.layers.uv.new("UVMap"); TILE = 4.0
        for f in bm.faces:
            n = f.normal; ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
            for l in f.loops:
                co = l.vert.co
                if az >= ax and az >= ay: u, v = co.x, co.y
                elif ax >= ay: u, v = co.y, co.z
                else: u, v = co.x, co.z
                l[uvl].uv = (u / TILE, v / TILE)   # 1 texture tile = 4 m
        bm.to_mesh(me); bm.free()
        if smooth:
            for p in me.polygons: p.use_smooth = True
            if hasattr(me, "use_auto_smooth"):
                me.use_auto_smooth = True; me.auto_smooth_angle = math.radians(32)
        ob = bpy.data.objects.new(self.name, me)
        scene.collection.objects.link(ob)
        return ob

def tangent_angle(rx, ry, a):
    r = math.radians(a)
    return math.atan2(ry * math.sin(r), rx * math.cos(r))

def mullions(g, rx, ry, z0, z1, step, mt="Mullion", skip=()):
    a = -180.0
    while a < 180:
        if not any(s0 <= a <= s1 for s0, s1 in skip):
            x, y, _ = P(rx + 0.04, ry + 0.04, a, 0)
            g.box(x, y, (z0 + z1) / 2, 0.12, 0.14, z1 - z0, mt, tangent_angle(rx, ry, a))
        a += step

# facade bays, angles in degrees (0 = front centre, +90 = right side)
BALCONIES = [(-20, 25, 2.4), (-80, -62, 1.4), (66, 84, 1.4), (150, 210, 1.6)]
FINS = [(-60, -41), (44, 64), (124, 142), (-142, -124)]
PIERS = [-20, 2, 25]
LEVELS = []   # for building.json

# ---------------------------------------------------------------- residential levels
for k in range(FIRST, LAST + 1):
    z0, z1 = zbase(k), zbase(k) + FH
    g = G("L%02d" % k)
    crown = k >= CROWN_FROM
    if crown:
        g.disc(RX + 2.3, RY + 2.3, z0, z0 + 0.45, 96, "White")
        g.wall(RX + 2.2, RY + 2.2, z0 + 0.45, z0 + 1.5, -180, 180, 96, "Rail")
        g.sector(RX + 2.1, RY + 2.1, RX + 2.3, RY + 2.3, z0 + 1.48, z0 + 1.54, -180, 180, 96, "Dark")
    else:
        g.disc(RX + 0.25, RY + 0.25, z0, z0 + 0.35, 96, "White")
    g.wall(RX, RY, z0 + 0.35, z1, -180, 180, 96, "Glass")
    mullions(g, RX, RY, z0 + 0.35, z1, 6.0)
    # interiors seen through the glass: soft rooms + a few lit units
    g.wall(RX - 1.8, RY - 1.8, z0 + 0.35, z1 - 0.1, -180, 180, 48, "Room")
    for _ in range(3):
        a = random.uniform(-150, 150)
        g.wall(RX - 1.75, RY - 1.75, z0 + 0.4, z1 - 0.2, a, a + random.uniform(8, 16), 4, "RoomLit")
    if not crown:
        for a0, a1, d in BALCONIES:
            g.sector(RX + 0.25, RY + 0.25, RX + d, RY + d, z0, z0 + 0.28, a0, a1, 24, "White")
            g.wall(RX + d - 0.05, RY + d - 0.05, z0 + 0.28, z0 + 1.35, a0, a1, 24, "Rail")
            g.sector(RX + d - 0.12, RY + d - 0.12, RX + d, RY + d, z0 + 1.33, z0 + 1.39, a0, a1, 24, "Dark")
    g.build()
    LEVELS.append({"name": "L%02d" % k, "label": "Level %d" % k, "z0": z0, "z1": z1,
                   "rx": RX + (2.4 if crown else 2.0), "ry": RY + (2.4 if crown else 2.0)})

# ---------------------------------------------------------------- facade fins + piers
g = G("Fins")
for a0, a1 in FINS:
    g.sector(RX - 0.2, RY - 0.2, RX + 0.6, RY + 0.6, BASE0, FIN_TOP, a0, a1, 8, "Stone")
    # horizontal reveal lines on the stone bands
    z = BASE0 + 0.8
    while z < FIN_TOP:
        g.sector(RX + 0.59, RY + 0.59, RX + 0.63, RY + 0.63, z, z + 0.05, a0, a1, 8, "Dark")
        z += 0.8
for a in PIERS:
    g.sector(RX - 0.1, RY - 0.1, RX + 2.5, RY + 2.5, BASE0, FIN_TOP, a - 1.3, a + 1.3, 2, "White")
g.build(smooth=False)

# ---------------------------------------------------------------- roof + penthouse
g = G("Roof")
g.disc(RX + 0.6, RY + 0.6, ROOF_Z, ROOF_Z + 0.6, 96, "White")
g.wall(RX + 0.5, RY + 0.5, ROOF_Z + 0.6, ROOF_Z + 1.7, -180, 180, 96, "Rail")
PH_Z = ROOF_Z + 0.6
g.box(0.5, -0.5, PH_Z + 2.6, 21.0, 15.0, 5.2, "White")
for lx in (-4.0, 6.0):                                   # louvred vents on the front face
    g.box(lx, -0.5 - 7.52, PH_Z + 2.8, 6.4, 0.06, 2.8, "Dark")
    for i in range(8):
        g.box(lx, -0.5 - 7.62, PH_Z + 1.55 + i * 0.34, 6.2, 0.18, 0.06, "White")
g.build(smooth=False)

# ---------------------------------------------------------------- core (elevator shaft)
g = G("Core")
g.box(0, 1.0, (P1_Z0 + ROOF_Z) / 2, 5.0, 5.0, ROOF_Z - P1_Z0, "Concrete")
g.build(smooth=False)

# ---------------------------------------------------------------- lobby (L01)
g = G("L01")
g.disc(PRX + 0.3, PRY + 0.3, 0.0, 0.2, 96, "Paving")
g.wall(PRX, PRY, 0.2, LOBBY_H, -180, 180, 120, "LobbyGlass")
mullions(g, PRX, PRY, 0.2, LOBBY_H, 4.0, skip=[(-7, 7)])
g.sector(PRX - 0.05, PRY - 0.05, PRX + 0.12, PRY + 0.12, 4.4, 4.55, -180, 180, 120, "Mullion")   # transom
PIER_A = [(-37, -30), (30, 37), (-82, -74), (74, 82), (150, 158), (-158, -150)]
for a0, a1 in PIER_A:
    g.sector(PRX - 0.6, PRY - 0.6, PRX + 0.7, PRY + 0.7, 0.0, LOBBY_H, a0, a1, 6, "Stone")
    x, y, _ = P(PRX + 0.75, PRY + 0.75, (a0 + a1) / 2, 0)
    g.box(x, y, 3.2, 0.25, 0.25, 0.4, "Light", tangent_angle(PRX, PRY, (a0 + a1) / 2))   # wall sconces
g.wall(PRX - 3.0, PRY - 3.0, 0.2, LOBBY_H - 0.3, 95, 265, 48, "LobbyWarm")
g.disc(PRX - 0.3, PRY - 0.3, 0.2, 0.25, 96, "Stone")              # warm interior
g.disc(PRX - 0.4, PRY - 0.4, LOBBY_H - 0.3, LOBBY_H - 0.2, 96, "LobbyWarm")
g.box(0, -2.0, 0.75, 7.0, 1.4, 1.1, "Stone")                                               # reception desk
for i, (R, z) in enumerate(((2.4, 6.4), (1.8, 5.6), (1.3, 4.9))):                           # ring pendants
    g.torus(0, -7.5, z, R, 0.07, "Light")
# entrance canopy + doors
g.box(0, -PRY - 1.9, 4.75, 13.0, 4.2, 0.45, "Dark")
for dx in (-3.6, -1.2, 1.2, 3.6):
    g.box(dx, -PRY - 0.05, 2.3, 0.12, 0.2, 4.2, "Dark")
g.box(0, -PRY - 0.05, 4.4, 9.6, 0.2, 0.15, "Dark")
for ix in range(-2, 3):                                                                   # canopy downlights
    g.box(ix * 2.4, -PRY - 1.9, 4.51, 0.3, 0.3, 0.03, "Light")
g.build()
LEVELS.insert(0, {"name": "L01", "label": "Lobby", "z0": 0.0, "z1": LOBBY_H, "rx": PRX + 0.8, "ry": PRY + 0.8})

# ---------------------------------------------------------------- podium canopy ring
g = G("Canopy")
CRX, CRY = 25.0, 19.5
g.sector(RX - 0.5, RY - 0.5, CRX, CRY, LOBBY_H, LOBBY_H + CANOPY_T, -180, 180, 128, "White")
for a in range(-180, 180, 12):
    x, y, _ = P(CRX - 1.6, CRY - 1.6, a, 0)
    g.box(x, y, LOBBY_H - 0.02, 0.28, 0.28, 0.04, "Light")
g.build()

# ---------------------------------------------------------------- plaza (ground)
g = G("Plaza")
g.disc(48, 40, P1_Z1, 0.0, 72, "Paving")
for bx in (-9, -3, 3, 9):                                           # bollards
    g.disc(0.16, 0.16, 0.0, 1.1, 12, "Steel", bx, -PRY - 7.5)
for sx in (-1, 1):
    g.disc(1.0, 1.0, 0.0, 1.1, 20, "Dark", sx * 7.2, -PRY - 4.2)    # planters
    g.sphere(sx * 7.2, -PRY - 4.2, 1.55, 0.95, "Green", sz=0.75)
    g.box(sx * 17, -PRY - 8, 0.25, 3.6, 1.2, 0.5, "Stone")           # benches
    g.box(sx * 17, -PRY - 8, 0.55, 3.2, 0.9, 0.1, "Wood")
g.build()

# ---------------------------------------------------------------- parking P1
g = G("P1")
H = P1_Z1 - P1_Z0
g.box(0, 0, P1_Z0 - 0.1, PW, PD, 0.2, "ConcFloor")
g.box(-PW / 2, 0, P1_Z0 + H / 2, 0.4, PD, H, "Concrete")
g.box(PW / 2, 0, P1_Z0 + H / 2, 0.4, PD, H, "Concrete")
g.box(0, -PD / 2, P1_Z0 + H / 2, PW, 0.4, H, "Concrete")
g.box(-(PW / 2 + 4) / 2, PD / 2, P1_Z0 + H / 2, PW / 2 - 4, 0.4, H, "Concrete")   # back wall, ramp gap
g.box((PW / 2 + 4) / 2, PD / 2, P1_Z0 + H / 2, PW / 2 - 4, 0.4, H, "Concrete")
COLS_X = [-21.5, -13, -4.5, 4.5, 13, 21.5]
COLS_Y = [-15, -5, 5, 15]
for cx in COLS_X:
    for cy in COLS_Y:
        g.box(cx, cy, P1_Z0 + H / 2, 0.75, 0.75, H, "Concrete")
        g.box(cx, cy, P1_Z0 + 1.0, 0.78, 0.78, 0.35, "Yellow")
for lx in (-17, -8.5, 8.5, 17, 0):
    for ly in range(-18, 19, 6):
        g.box(lx, ly, P1_Z1 - 0.45, 0.25, 3.0, 0.06, "Tube")
for px in (-19, -10, 10, 19):
    g.box(px, 0, P1_Z1 - 0.65, 0.16, PD - 1, 0.16, "Red")
for row_y in (-10, 10):                                             # stall lines
    for x in range(-27, 28, 3):
        if abs(x) < 4: continue
        g.box(x, row_y, P1_Z0 + 0.01, 0.1, 5.2, 0.01, "Paint")
    g.box(-15.5, row_y - 2.6 * (1 if row_y < 0 else -1), P1_Z0 + 0.01, 23, 0.1, 0.01, "Paint")
    g.box(15.5, row_y - 2.6 * (1 if row_y < 0 else -1), P1_Z0 + 0.01, 23, 0.1, 0.01, "Paint")
CARS = [(-22.5, -10, "CarSilver"), (-11.5, -10, "CarDark"), (14.5, -10, "CarSilver"),
        (-17.5, 10, "CarDark"), (8.5, 10, "CarSilver"), (20.5, 10, "CarDark")]
for cx, cy, cm in CARS:
    g.box(cx, cy, P1_Z0 + 0.6, 1.85, 4.6, 0.75, cm)
    g.box(cx, cy + 0.2, P1_Z0 + 1.25, 1.6, 2.4, 0.6, cm)
    for wx in (-0.85, 0.85):
        for wy in (-1.4, 1.5):
            g.box(cx + wx, cy + wy, P1_Z0 + 0.32, 0.25, 0.65, 0.65, "CarDark")
# ramp up to grade at the back, centred (like the reference)
g.poly([(-3.8, 14.0, P1_Z0 + 0.01), (3.8, 14.0, P1_Z0 + 0.01), (3.8, PD / 2 + 4, P1_Z1 - 1.0), (-3.8, PD / 2 + 4, P1_Z1 - 1.0)], "ConcFloor")
for sx in (-1, 1):
    g.box(sx * 4.3, 14 + (PD / 2 + 4 - 14) / 2, P1_Z0 + H / 2, 0.3, PD / 2 + 4 - 14, H, "Concrete")
    for yy in (17, 21, 25):
        g.box(sx * 4.12, yy, P1_Z0 + 1.6 + (yy - 14) * 0.24, 0.06, 0.2, 0.35, "Light")
for sx in (-1, 1):
    g.box(sx * 4.0, 14 + (PD / 2 + 4 - 14) / 2, P1_Z0 + 0.15, 0.25, PD / 2 + 4 - 14, 0.3, "Yellow")   # curbs
CEIL = P1_Z1 - 0.05
g.box(-17.0, 0, CEIL, PW / 2 - 4, PD, 0.1, "Concrete")
g.box(17.0, 0, CEIL, PW / 2 - 4, PD, 0.1, "Concrete")
g.box(0, (-PD / 2 + 14) / 2, CEIL, 8.0, 14 + PD / 2, 0.1, "Concrete")
g.box(0, PD / 2 + 4.05, P1_Z1 - 0.5, 7.6, 0.1, 1.0, "Daylight")
g.build(smooth=False)
LEVELS.insert(0, {"name": "P1", "label": "P1", "z0": P1_Z0, "z1": P1_Z1, "rect": [PW, PD]})

# ---------------------------------------------------------------- render setup (previews only)
eng = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
scene.render.engine = eng
ee = scene.eevee
for attr, val in (("use_ssr", True), ("use_ssr_refraction", True), ("use_gtao", True), ("use_bloom", True),
                  ("taa_render_samples", 48), ("use_soft_shadows", True), ("shadow_cube_size", '1024'), ("shadow_cascade_size", '2048')):
    if hasattr(ee, attr):
        try: setattr(ee, attr, val)
        except Exception: pass
scene.render.resolution_x, scene.render.resolution_y = 1600, 900
scene.render.image_settings.file_format = 'PNG'
try: scene.view_settings.view_transform = 'AgX'
except Exception: scene.view_settings.view_transform = 'Filmic'

world = bpy.data.worlds.new("Sky"); scene.world = world; world.use_nodes = True
nt = world.node_tree; bg = nt.nodes["Background"]
bg.inputs["Color"].default_value = (*srgb("8DB2E6"), 1)
bg.inputs["Strength"].default_value = 0.9

render_objs = []
def light(name, kind, loc, rot=(0, 0, 0), energy=1.0, color=(1, 1, 1), size=None):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color
    if size is not None and hasattr(ld, "size"): ld.size = size
    ob = bpy.data.objects.new(name, ld); ob.location = loc; ob.rotation_euler = rot
    scene.collection.objects.link(ob); render_objs.append(ob); return ob

light("Sun", 'SUN', (0, 0, 100), (math.radians(62), 0, math.radians(-50)), 5.5, srgb("FFDDB0"))
for x in (-17, 0, 17):
    for y in (-12, 0, 12):
        light("ParkLight", 'AREA', (x, y, P1_Z1 - 0.6), (0, 0, 0), 600, srgb("FFF0DA"), 3.0)

def camera(name, loc, target, lens):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 2000
    ob = bpy.data.objects.new(name, cd); ob.location = loc
    scene.collection.objects.link(ob); render_objs.append(ob)
    import mathutils
    d = mathutils.Vector(target) - mathutils.Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob

shots = [("preview_front",    camera("CamFront",    (0, -140, 3.0), (0, 0, 40), 26)),
         ("preview_entrance", camera("CamEntrance", (0, -43, 2.2), (0, 0, 7.5), 24)),
         ("preview_parking",  camera("CamParking",  (0, -21, P1_Z0 + 1.6), (0, 20, P1_Z0 + 1.3), 22))]

# ---------------------------------------------------------------- save + export
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "fci_tower.blend"))

glb = os.path.join(OUT, "fci_tower.glb")
kw = dict(filepath=glb, export_format='GLB', use_selection=False, export_cameras=False, export_image_format='AUTO',
          export_lights=False, export_apply=True, export_yup=True)
try:
    bpy.ops.export_scene.gltf(**kw, export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6)
    draco = True
except Exception as e:
    print("Draco export failed, exporting plain GLB:", e)
    bpy.ops.export_scene.gltf(**kw); draco = False

# building.json in three.js coordinates (x, y=up, z=front)
info = {"units": "m", "frontAxis": "+z", "draco": draco,
        "tower": {"rx": RX, "ry": RY}, "podium": {"rx": PRX, "ry": PRY},
        "roof": {"y": ROOF_Z, "penthouse": {"x": 0.5, "z": 0.5, "w": 21, "d": 15, "y0": PH_Z, "y1": PH_Z + 5.2}},
        "entrance": {"x": 0, "z": PRY + 1.9, "y": 4.75, "w": 13, "d": 4.2},
        "core": {"x": 0, "z": -1.0, "w": 5, "d": 5, "y0": P1_Z0, "y1": ROOF_Z},
        "levels": [{**L, "y0": L["z0"], "y1": L["z1"]} for L in LEVELS]}
for L in info["levels"]: L.pop("z0"); L.pop("z1")
with open(os.path.join(OUT, "building.json"), "w") as fh: json.dump(info, fh, indent=1)

# ---------------------------------------------------------------- previews (render-only extras)
gnd = G("RenderGround"); gnd.disc(600, 600, -0.6, -0.42, 64, "Paving"); render_objs.append(gnd.build(smooth=False))
for sx in (-1, 1):
    for i in range(6):                                   # simple street trees for scale
        t = G("RenderTree"); x = sx * (34 + i * 9); y = -32 - (i % 2) * 6
        t.disc(0.25, 0.25, 0.0, 4.0, 8, "Wood", x, y); t.sphere(x, y, 6.5, 3.4, "Green", sz=0.9)
        t.build()
for fname, cam in shots:
    scene.camera = cam
    bg.inputs["Strength"].default_value = 0.04 if "parking" in fname else 0.9
    scene.render.filepath = os.path.join(OUT, fname + ".png")
    bpy.ops.render.render(write_still=True)

print("FCI_BUILD_OK glb=%.2fMB time=%.0fs engine=%s" % (os.path.getsize(glb) / 1e6, time.time() - T0, eng))
