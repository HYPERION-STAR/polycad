# PolyCAD — Derinlemesine Teknik Anlatı

## 0. Mimari Genel Bakış

Proje **dört katmanlı** bir Qt+OpenGL uygulaması. Her katman tek bir sorumluluk taşıyor ve aşağıdan yukarıya şu hiyerarşide:

```
┌──────────────────────────────────────────────────────┐
│  window.py     — Orchestration / Controller          │
│                  (panelleri bağlar, undo komutları)  │
├──────────────────────────────────────────────────────┤
│  ui.py         — View widgets (Toolbar, Tree, Props) │
│  viewport.py   — 3D View + Gizmo + Picking           │
├──────────────────────────────────────────────────────┤
│  scene.py      — Model: Document, BaseObject         │
│                  Pure data, GUI'den habersiz         │
├──────────────────────────────────────────────────────┤
│  main.py       — Bootstrap (QApplication, stylesheet)│
└──────────────────────────────────────────────────────┘
```

Bu MVC'nin gevşek bir varyantı. **Model** (`Document` + `BaseObject`) Qt widget'larına hiçbir referans tutmuyor — saf veri katmanı. **View** (`OpenGLWidget`, paneller) modelden okuma yapıyor. **Controller** (`MainWindow`) ikisini sinyal/slot ile birbirine bağlıyor.

---

## 1. Sahnedeki Bir Kutu Nerede Saklanıyor?

Bu sorunun cevabı kritik çünkü **aynı kutu üç farklı yerde yaşıyor**, her yerin amacı farklı.

Bir Box eklendiğinde olan şey:

```python
# window.py _add_primitive()
positions, normals, indices = factory()      # Geometri üretildi
obj = BaseObject(name=name)                  # Mantıksal nesne yaratıldı
obj.set_color(*color)
mesh_item = self.gl_widget.add_primitive(    # GPU'ya gönderildi
    name=name, positions=positions, normals=normals,
    indices=indices, color=color)
doc.add_object(obj)                          # Document'a kaydedildi
obj._mesh_item = mesh_item                   # Köprü kuruldu
obj._factory = factory                       # Geometri reproduction için saklandı
```

Sonuçta **üç paralel kayıt** oluştu:

### 1.1 `Document._objects` listesi — Mantıksal Sahne

`scene.py` içindeki Document, sahnenin "doğruluk kaynağı"dır:

```python
class Document:
    def __init__(self):
        self._objects: list[BaseObject] = []
        self._selected_ids: set[int] = set()
```

Burada saklanan `BaseObject`, **sadece** mantıksal özellikleri tutar: ID, isim, pozisyon, rotasyon, scale, renk. **Mesh verisi (vertex array) Document'a girmez** — bu kritik bir tasarım kararı.

```python
class BaseObject:
    def __init__(self, name="", color=None):
        self._id = BaseObject.next_id
        BaseObject.next_id += 1
        self.position       = np.array([0.,0.,0.], dtype=np.float32)
        self.rotation_euler = np.array([0.,0.,0.], dtype=np.float32)
        self.scale          = np.array([1.,1.,1.], dtype=np.float32)
        self.color          = np.array(color or [0.7,0.7,0.85], dtype=np.float32)
```

Neden? Çünkü mantıksal model GPU'ya bağımlı olmamalı. Bir Box'ın "8 vertex + 12 face" gerçeğini bilmesi gerekmez; o sadece "ben bir Box'ım, şu pozisyondayım" der.

### 1.2 `OpenGLWidget._objects` listesi — Render Tarafı Cache

`viewport.py` paralel bir liste tutuyor ama içerik farklı:

```python
self._objects.append({
    'mesh': mesh_item,                       # pyqtgraph GLMeshItem referansı
    'name': name,
    'position': np.array([0.0, 0.0, 0.0]),  # Çakışma testi için cache'lenmiş kopya
    'size': self._estimate_size(vertexes),  # AABB boyutu
    'factory': None,
})
```

Bu liste **render katmanının** kendi defteri — pozisyonu burada da tutmasının nedeni: yeni nesne eklenirken `get_object_at_position()` çakışma kontrolü yapacak ve her `Document` sorgusu pahalı; yerel cache hızlı.

```python
def get_object_at_position(self, spacing):
    for attempt in range(16):
        col, row = attempt % 4, attempt // 4
        candidate_pos = np.array([(col-1.5)*spacing, 0.0, (row-0.5)*spacing])
        for obj in self._objects:                    # Burası — viewport'un kendi listesi
            other_size = obj.get('size', np.array([1.0, 1.0, 1.0]))
            other_pos  = obj['position']
            min_dist   = (other_size + np.array([0.5,0.5,0.5])) / 2.0
            if abs(candidate_pos[0] - other_pos[0]) < min_dist[0] and ...:
                has_collision = True; break
        if not has_collision: return candidate_pos
```

Yani aynı pozisyon iki yerde: Document'ta canonical, viewport'ta perf cache. Senkronizasyon `_apply_transform_to_mesh()` içinde yapılıyor:

```python
for tracked in self.gl_widget._objects:
    if tracked['mesh'] is mesh_item:
        tracked['position'] = obj.position.copy()
        break
```

### 1.3 GPU'daki Vertex Buffer — pyqtgraph Tarafı

Üçüncü kopya pyqtgraph'ın `GLMeshItem` içinde:

```python
# viewport.py add_primitive()
mesh_data = gl.MeshData(vertexes=vertexes, faces=faces)
face_colors = np.zeros((num_faces, 4), dtype=np.float32)
face_colors[:, :3] = color; face_colors[:, 3] = 1.0
mesh_data.setFaceColors(face_colors)

mesh_item = gl.GLMeshItem(
    meshdata=mesh_data,
    smooth=True, computeNormals=True,
    shader='shaded', drawFaces=True, drawEdges=False,
)
```

`gl.MeshData` numpy array'leri tutar ve pyqtgraph render sırasında VBO'ya yükler. Bizim koda göre **vertex array** burada yaşar — `BaseObject` bunu görmez.

### 1.4 Köprü: `obj._mesh_item`

Mantıksal nesneyle GL mesh'i arasındaki köprü çok basit bir Python attribute:

```python
obj._mesh_item = mesh_item                   # window.py _add_primitive sonunda
```

Property panelinden renk değişince:
```python
def _on_color_changed(self, obj):
    mesh_item = getattr(obj, '_mesh_item', None)  # Köprüden ulaş
    if mesh_item is not None:
        self.gl_widget.update_mesh_color(mesh_item, color_rgb)
```

Bu, BaseObject'in mesh hakkında zorunlu bilgisi olmaması gibi temiz bir ayrım istemekle, pratik bir köprü ihtiyacı arasındaki uzlaşmadır.

---

## 2. Tek Bir Tıklamanın Yolu — End-to-End Akış

"Toolbar'da Box butonuna tıkladım" demenin perde arkası:

```
QPushButton.clicked  →  functools.partial(_add_primitive, factory, "Box")
                         │
                         ▼
                     window._add_primitive()
                         │
              ┌──────────┼──────────────┬─────────────┐
              ▼          ▼              ▼             ▼
        factory()    BaseObject()  add_primitive()  Document.add_object()
        (geometri)   (mantıksal)   (GL mesh)         (kayıt)
                                       │
                                       ▼
                                  doc.push_command(AddObjectCommand)
                                       │
                                       ▼
                                  object_tree.update_tree()
                                  prop_panel.update_for_object(obj)
```

Toolbar bağlantısı:
```python
def make_callback(prim_name: str):
    factory = PRIMITIVE_FACTORIES[prim_name]
    return functools.partial(self._add_primitive, factory, prim_name.title())

for prim in ("box", "cylinder", "sphere", "cone"):
    btn = getattr(self.toolbar, f"_btn_{prim}")
    btn.clicked.connect(make_callback(prim))
```

`functools.partial` neden? Çünkü Qt `clicked` sinyali parametresiz çağrı bekler. `lambda` kullanırsak Python closure'un geç bağlama (late binding) sorunu yüzünden tüm butonlar son iterasyondaki `prim` değerini kullanır. `partial` argümanı **anlık** yakalar.

---

## 3. Seçim Sistemi — İki Yönlü Senkron

Seçim üç yerde temsil ediliyor:

1. `Document._selected_ids: set[int]` — canonical
2. `BaseObject.selected: bool` — her nesne kendi durumunu bilir
3. `QTreeWidgetItem.setSelected()` — UI gösterimi
4. `OpenGLWidget._selected_obj` — gizmo'nun kime bağlı olduğu

Setter'a `_selected_ids` atandığında otomatik fan-out oluyor:

```python
@selected_ids.setter
def selected_ids(self, value):
    for obj in self._objects:
        obj.selected = obj.id in value     # her BaseObject'in flag'i güncellenir
    self._selected_ids = value
```

UI üzerinde tıklama olursa:
```python
# ui.py ObjectTreePanel
def _on_item_clicked(self, item):
    object_id = item.data(0, _ID_ROLE)
    if object_id is not None:
        doc.selected_ids = {object_id}     # Setter chain reaction'ı başlatır
```

`_ID_ROLE = Qt.ItemDataRole.UserRole`. Qt tree item'larında veri saklamak için **role** mekanizması kullanılıyor; bu standart Qt pattern'idir. `Qt.DisplayRole` görsel metni, `UserRole` ise programatik veri tutar.

Viewport tıklamasında:
```python
# viewport.py
def _on_left_press(self, event):
    hit_obj = self._pick_object(mx, my)
    if hit_obj is not None:
        self._select_object(hit_obj)         # Sadece local _selected_obj atar
                                              # MainWindow signal'i alıp Document'ı günceller
```

Sinyal akışı:
```python
# viewport.py
viewport_object_selected = Signal(object)

# window.py _setup_panels
self.gl_widget.viewport_object_selected.connect(self._on_viewport_select)

def _on_viewport_select(self, obj):
    if obj is not None:
        doc.selected_ids = {obj.id}          # ← Burada Document'a yazılır
        self.prop_panel.update_for_object(obj)
        self.object_tree.update_tree()
```

Bu pattern'ın amacı: viewport pure-view kalsın, model değişikliği MainWindow controller'ı üzerinden gitsin.

---

## 4. Property Panel — Çift Aşamalı Edit

Spinbox'a yazınca canlı önizleme istiyorsun ama her tuş vuruşunda undo komutu istemiyorsun. Çözüm:

```python
def _on_value_changed(self):                  # Her değer değişiminde
    if self._updating or self._current_obj is None:
        return
    if self._pending_old_data is None:
        self._pending_old_data = self._current_obj.to_data()  # İlk değişimde snapshot
    self.apply_changes()                       # Modeli güncelle
    self.transform_changed.emit(self._current_obj)  # Mesh'i güncelle

def _on_editing_finished(self):                # Spinbox focus kaybedince
    if self._pending_old_data is not None:
        new_data = self._current_obj.to_data()
        if self._pending_old_data.model_dump() != new_data.model_dump():
            self.property_edit_finished.emit(
                self._current_obj, self._pending_old_data, new_data
            )                                  # ← Undo komutu burada doğar
        self._pending_old_data = None
```

`_pending_old_data` mekanizması: spinbox'a girilen ilk değerde "düzenlemeye başladım" tetikleyicisi olarak snapshot alır. Sonraki değişiklikler bu snapshot'a dokunmaz. Edit bitince eski + yeni state karşılaştırılır, gerçekten değişmişse undo command push'lanır.

`_updating` bayrağı re-entrancy koruması:
```python
def update_for_object(self, obj):
    self._updating = True
    spin.setValue(float(obj.position[i]))     # Bu valueChanged'i tetikler
    # ...
    self._updating = False
```

Eğer bayrak olmasaydı: panel programatik güncellenirken `valueChanged` tetiklenir → `_on_value_changed` çağrılır → `apply_changes` yine spinbox'tan okuyup obje'ye yazar → potansiyel sonsuz döngü ya da yanlış undo başlangıcı.

---

## 5. Transform Uygulama — Matrix Compose

```python
def _apply_transform_to_mesh(self, obj):
    tr = pg.Transform3D()
    tr.translate(*obj.position)
    tr.rotate(math.degrees(obj.rotation_euler[0]), 1, 0, 0)
    tr.rotate(math.degrees(obj.rotation_euler[1]), 0, 1, 0)
    tr.rotate(math.degrees(obj.rotation_euler[2]), 0, 0, 1)
    tr.scale(*obj.scale)
    mesh_item.setTransform(tr)
```

Burada **çağrı sırası ≠ matematiksel uygulama sırası**. Qt'nin `QMatrix4x4` ailesinden gelen `Transform3D` **post-multiply** yapar; yani çağrı sırası şu matrisi inşa eder:

```
M = T · Rx · Ry · Rz · S
```

Bir vertex `v` için: `v' = M·v = T·(Rx·(Ry·(Rz·(S·v))))` — yani önce scale uygulanır, sonra rotation (Z, Y, X sırası), en son translate. Bu, klasik graphics pipeline ile uyumlu.

`obj.rotation_euler` **radyan** cinsinden saklanıyor, `tr.rotate` ise **derece** ister, bu yüzden her seferinde `math.degrees(...)` çevrimi var. Niye radyan saklanmış? `numpy.radians`/`degrees` ile pydantic serileştirme arasında bir tasarım kararı; muhtemelen iç hesaplamalarda (trigonometri) radyan daha kullanışlı görülmüş.

---

## 6. Gizmo Drag — Ekran Uzayında Matematik

Bir nesneyi X ekseninde sürüklemek 3D bir problem ama mouse delta 2D. Çözüm:

```python
def _on_drag_move(self, event):
    obj_pos  = obj.position
    axis_dir = MoveGizmo.AXIS_DIRS[self._dragging_axis]   # örn. (1,0,0)

    screen_start = self._world_to_screen(obj_pos)
    screen_end   = self._world_to_screen(obj_pos + axis_dir)
    sdx, sdy = screen_end[0]-screen_start[0], screen_end[1]-screen_start[1]
    screen_len = math.sqrt(sdx*sdx + sdy*sdy)

    proj = (dx*sdx + dy*sdy) / screen_len      # mouse delta'nın eksen yönü bileşeni
    world_delta = proj / screen_len            # px → world unit
    obj.position += axis_dir * world_delta
```

Adım adım:
1. Eksen yönünü dünya uzayında 1 birim uzat → ekrana projelendir → ekrandaki yönü ve uzunluğu bul.
2. Mouse delta'sını bu ekran-yönü vektörüne dot product ile izdüşür (`proj`).
3. `screen_len` ekranda 1 world unit'in kaç piksel olduğunu söyler. Yani `1 / screen_len` = 1 piksel kaç world unit demek.
4. `proj * (1/screen_len)` mouse delta'nın world karşılığı.

Bu yöntem **perspektif farkındalığını** otomatik halleder: kamera nesneye yakınsa `screen_len` büyür → drag yavaşlar (1 piksel daha az hareket). Kamera uzaksa tersi. Doğal his.

`_world_to_screen` ise klasik MVP pipeline:
```python
clip = pm.map(vm.map(QVector4D(*world_pos, 1.0)))     # view → clip
ndcx, ndcy = clip.x()/clip.w(), clip.y()/clip.w()     # perspective divide → NDC
sx = (ndcx + 1.0) * 0.5 * vw                          # NDC → pixel
sy = (1.0 - ndcy) * 0.5 * vh                          # Y-flip (Qt top-down)
```

---

## 7. Undo Sistemi — Command Pattern

Üç komut sınıfı: `AddObjectCommand`, `DeleteObjectsCommand`, `ModifyObjectCommand`.

Her komut `undo()` ve `redo()` metotlarını implement eder. Document iki deque tutar:

```python
def push_command(self, command):
    self._undo_stack.append(command)
    while self._redo_stack:                  # Yeni komut → redo zinciri ölü
        self._redo_stack.popleft()

def undo(self):
    if not self._undo_stack: return False
    cmd = self._undo_stack.pop()
    cmd.undo()
    self._redo_stack.append(cmd)             # undo edilen komut redo'ya geçer
    return True
```

Klasik git'in `HEAD~1` mantığı: undo bir komutu üst yığından alıp redo yığınına atar. Yeni bir değişiklik yapıldığında redo yığını temizlenir (çünkü artık branch'lendin).

`ModifyObjectCommand`'in inceliği: nesneye referans tutmuyor, **ID** tutuyor:

```python
class ModifyObjectCommand:
    def __init__(self, window, obj, old_data, new_data):
        self._obj_id = obj.id              # Referans değil
        self._old_data = old_data
        self._new_data = new_data

    def _apply_data(self, data, msg):
        obj = doc.get_object_by_id(self._obj_id)   # Her seferinde yeniden bul
        if obj:
            obj.from_data(data)
            self._window._apply_transform_to_mesh(obj)
```

Neden? Çünkü nesne silinip undo ile geri gelirse, geri gelen nesnenin Python `id()` farklı bile olabilir ama ID alanı aynı kalır. Bu, command pattern'in ortak sağlamlık tekniğidir.

`old_data`/`new_data` ise `ObjectData` pydantic modeli — tamamen serileştirilebilir snapshot:

```python
class ObjectData(BaseModel):
    name: str
    color:    list[float]
    position: list[float]
    rotation: list[float]      # Derece cinsinden
    scale:    list[float]
```

Karşılaştırma `model_dump()` ile:
```python
if self._pending_old_data.model_dump() != new_data.model_dump():
```
`model_dump()` pydantic modeli dict'e çevirir → eşitlik kontrolü doğal Python dict karşılaştırması olur.

---

## 8. Disk Format — OBJ + Embedded Metadata

Export sırasında transform'lar OBJ comment'ine gömülüyor:

```python
f.write(f"o {obj.name}\n")
f.write(f"# PolyCADData: color {obj.color[0]:.6f} {obj.color[1]:.6f} {obj.color[2]:.6f}\n")
f.write(f"# PolyCADData: pos   {obj.position[0]:.6f} ...\n")
f.write(f"# PolyCADData: rot   {obj.rotation_euler[0]:.6f} ...\n")
f.write(f"# PolyCADData: scale {obj.scale[0]:.6f} ...\n")

# Vertex'ler LOCAL koordinatlarda, transform UYGULANMAMIŞ
for i in range(num_verts):
    px, py, pz = positions[i]
    f.write(f"v {px:.6f} {py:.6f} {pz:.6f}\n")
```

Bu yaklaşımın güzelliği:
- Diğer OBJ okuyucular (Blender, MeshLab) `#` ile başlayan satırları yorum olarak es geçer.
- PolyCAD reimport ettiğinde comment'leri parse edip transform'u geri yükler.
- Vertex'ler local kaldığı için ileride non-uniform scale'i bozmadan tekrar düzenleyebilirsin.

Import tarafında parser:
```python
if line.startswith("# PolyCADData:"):
    parts = line.split()
    if len(parts) >= 6:
        key  = parts[2]                              # "color" / "pos" / "rot" / "scale"
        vals = (float(parts[3]), float(parts[4]), float(parts[5]))
        current_metadata[key] = vals
```

Üçüncü taraf OBJ (metadata yok) için **otomatik centerlama** yapılıyor:

```python
if 'pos' not in metadata and len(positions) > 0:
    min_bounds = np.min(positions, axis=0)
    max_bounds = np.max(positions, axis=0)
    centroid   = (min_bounds + max_bounds) / 2.0
    positions  = positions - centroid              # Vertex'leri origin'e taşı
    obj.position = np.array(centroid, dtype=np.float32)  # Pozisyon olarak sakla
```

Neden? Bazı OBJ dosyaları vertex'leri uzayın çok uzak bir yerinde tanımlar (örn. milyonlarca birim öteden). Bu yapılmasa gizmo nesneden çok uzakta belirir, kullanıcı seçemez. Centroid çıkarıp pozisyona koyduğumuzda **görsel sonuç değişmez** ama pivot mesh'in merkezinde olur.

### Vertex Deduplication

OBJ face syntax'ı (`v/vt/vn`) aynı vertex pozisyonu için farklı normal/UV taşıyabilir. Parser bunu `(vi, ni)` çifti üzerinden dedup ediyor:

```python
unique_verts = {}                # (vi, ni) → new_index
for face_verts in current_faces:
    for tri in range(1, len(face_verts) - 1):     # Fan triangulation
        for local_idx in (0, tri, tri + 1):
            vi, ni = face_verts[local_idx]
            key = (vi, ni)
            if key not in unique_verts:
                idx = len(out_positions)
                unique_verts[key] = idx
                out_positions.append(all_verts[vi])
                out_normals.append(all_normals[ni] if 0 <= ni < len(all_normals)
                                   else [0., 1., 0.])
            out_indices.append(unique_verts[key])
```

**Fan triangulation**: bir N-gon face (örn. quad) için `(v0, v1, v2)`, `(v0, v2, v3)`, ... şeklinde üçgenlere bölünür. İlk vertex tüm üçgenlerde paylaşılır → "fan".

`(vi, ni)` key seçimi şu sonuca yol açar:
- Aynı pozisyon **aynı normal** ile birden çok yerde geçiyorsa → tek vertex (smooth shading)
- Aynı pozisyon **farklı normal** ile geçiyorsa → ayrı vertex (hard edge korunur, örn. küpün köşeleri)

---

## 9. FPS Sayacı — Monkey Patching

```python
def _hook_fps_counter(self):
    original_paint = self.gl_widget._gl_view.paintGL
    def counting_paint():
        self._frame_count += 1
        original_paint()
    self.gl_widget._gl_view.paintGL = counting_paint
```

pyqtgraph'ın `GLViewWidget.paintGL` metodu instance üzerine yazılıyor. Python'da metot bir attribute olduğu için bu legal. Wrapper hem counter'ı artırır hem orijinali çağırır.

Saniyede bir QTimer hesaplama yapar:
```python
self._fps_timer.setInterval(1000)
self._fps_timer.timeout.connect(self._update_fps_display)

def _update_fps_display(self):
    elapsed_ms = self._fps_elapsed.elapsed()
    if elapsed_ms > 0:
        self._fps = self._frame_count * 1000.0 / elapsed_ms
    self.fps_label.setText(f"FPS: {self._fps:.0f}")
    self._frame_count = 0
    self._fps_elapsed.restart()
```

`QElapsedTimer` `QTimer`'dan ayrı; `QTimer` callback zamanlaması idealden saparsa `elapsed_ms` gerçek geçen süreyi söyler, FPS daha doğru hesaplanır.

---

## 10. Stylesheet ve Font Pipeline

`main.py`'deki `_get_stylesheet()` çok büyük bir CSS string'i. Önemli olan, **çalışma zamanında ikon yolu enjekte etmesi**:

```python
_ascii_dir = os.path.join(tempfile.gettempdir(), "polycad_icons")
os.makedirs(_ascii_dir, exist_ok=True)
for _name in ("arrow_up.png", "arrow_down.png"):
    shutil.copyfile(os.path.join(_icons_dir, _name),
                    os.path.join(_ascii_dir, _name))
_arrow_up = os.path.join(_ascii_dir, "arrow_up.png").replace("\\", "/")
...
css = css.replace("%%ARROW_UP%%",   _arrow_up)
css = css.replace("%%ARROW_DOWN%%", _arrow_down)
```

CSS template'inde:
```
QDoubleSpinBox::up-arrow {
    image: url("%%ARROW_UP%%");
    width: 9px;
    height: 7px;
}
```

`%%TOKEN%%` substitution Python tarafında. Neden gerekli? Qt stylesheet `url()` parser'ı **non-ASCII karakter** içeren yolları çözemiyor. `Masaüstü` gibi bir yol direkt yazılırsa ikonlar gözükmez. ASCII güvenli `%TEMP%` dizinine kopyalama bu sorunu çözer.

Font fallback:
```python
QFont.insertSubstitutions("Segoe UI", ["Segoe UI Emoji", "Segoe UI Symbol"])
```

`Segoe UI` font'unda glyph bulunmadığında Qt önce `Segoe UI Emoji`, sonra `Segoe UI Symbol` font'larından glyph arar. Toolbar'daki ⬜⬡⬤▲, panellerdeki 📍🔄📐🎨 karakterleri için kritik.

---

## 11. Bütün Bağlantıların Haritası — Sinyal/Slot

Bu uygulamanın "neyin nereye bağlandığı" tablosu:

| Olay (signal kaynağı)                     | Slot (window.py)                                            | Etki                                    |
| ----------------------------------------- | ----------------------------------------------------------- | --------------------------------------- |
| Toolbar Box/Cylinder/.../wireframe/delete | `_add_primitive` / `_toggle_wireframe` / `_delete_selected` | Sahneyi değiştirir                      |
| `object_tree.tree.currentItemChanged`     | `_on_selection_change`                                      | Selection'ı Document'a yansıtır         |
| `prop_panel.transform_changed`            | `_on_transform_changed`                                     | `_apply_transform_to_mesh` + gizmo sync |
| `prop_panel.color_changed`                | `_on_color_changed`                                         | Mesh face color update                  |
| `prop_panel.property_edit_finished`       | `_on_property_edit_finished`                                | Undo command push                       |
| `gl_widget.viewport_object_selected`      | `_on_viewport_select`                                       | Document selection + tree + props sync  |
| `gl_widget.viewport_object_moved`         | `_on_viewport_move`                                         | Live mesh transform                     |
| `gl_widget.viewport_drag_finished`        | `_on_property_edit_finished`                                | Undo command push (drag bitince)        |

İki yönlü senkronun bir örneği — gizmo drag'i:
```
mouse drag → viewport._on_drag_move
           → obj.position güncellenir
           → viewport_object_moved emit
           → window._on_viewport_move
           → _apply_transform_to_mesh(obj)   # mesh visual güncel
           → prop_panel.update_for_object(obj)  # spinbox'lar yeni değeri gösterir
mouse release → viewport._finish_drag
              → viewport_drag_finished emit (obj, old_data, new_data)
              → window._on_property_edit_finished
              → ModifyObjectCommand push   # Undo'lanabilir
```

---

## 12. Memory Sahipliği Özeti

| Veri                       | Kim sahip                                                         | Yaşam süresi                            |
| -------------------------- | ----------------------------------------------------------------- | --------------------------------------- |
| Vertex/normal/index arrays | `gl.MeshData` içinde (pyqtgraph)                                  | Mesh item silinene kadar                |
| `BaseObject` (mantıksal)   | `Document._objects` listesi                                       | Document hayatta kalana kadar           |
| Transform değerleri        | `BaseObject.position/rotation_euler/scale`                        | BaseObject ile                          |
| Renk                       | `BaseObject.color` (canonical) + `MeshData.faceColors` (gpu copy) | İki yerde, manuel sync                  |
| Pozisyon cache             | `OpenGLWidget._objects[i]['position']` (perf cache)               | Collision detection için                |
| Mesh köprüsü               | `obj._mesh_item` (Python attribute)                               | İki yöndeki erişim için                 |
| Undo state                 | `ObjectData` pydantic snapshot, deque'ler içinde                  | Document hayatı boyunca, sınırsız büyür |

---

## "Storage Pattern" Sorusu Sorulursa Tek Cümleyle

**PolyCAD model ile render verisini ayırır**: mantıksal sahne `Document._objects` içinde `BaseObject`'ler olarak yaşar (sadece transform + renk + ID); GPU mesh verisi ise pyqtgraph `GLMeshItem` içinde tutulur; ikisi `obj._mesh_item` Python attribute'u ile köprülenir; disk format olarak vanilla OBJ kullanılır ama transform/renk meta-verisi `# PolyCADData:` yorum satırlarına gömülerek round-trip uyumluluğu sağlanır; undo sistemi pydantic `ObjectData` snapshot'larını ID üzerinden referanslayan Command pattern ile çalışır.

Daha derin gitmemi istediğin spesifik bir nokta var mı? (Rendering pipeline, OBJ parser detayları, Qt event filter mekaniği — hangisi olursa.)