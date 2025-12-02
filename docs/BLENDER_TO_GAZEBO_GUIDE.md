# Blender to Gazebo Model Pipeline

Bu rehber, Blender'da oluşturulan 3D modellerin Gazebo simülasyonuna nasıl aktarılacağını açıklar.

---

## Genel Bakış

```
Blender Model → Export (.dae) → model.sdf + model.config → Gazebo World
```

## Blender Ayarları

### 1. Ölçek (Scale)

**Kritik:** Blender'da 1 unit = 1 metre olmalı.

```
Blender Preferences → Add-ons → "Unit System" → Metric
Scene Properties → Unit System → Metric
Scene Properties → Unit Scale → 1.0
```

### 2. Koordinat Sistemi

Gazebo ve Blender farklı koordinat sistemleri kullanır:

| Eksen | Blender | Gazebo |
|-------|---------|--------|
| Yukarı | Z | Z |
| İleri | -Y | X |
| Sağ | X | Y |

**Export sırasında otomatik dönüşüm yapılır.**

---

## Model Oluşturma Kuralları

### Adlandırma (Naming Convention)

```
model_name/
├── model.config      # Metadata
├── model.sdf         # Fizik ve görsel tanımlar
└── meshes/
    └── model_name.dae  # Mesh dosyası
```

- Model ismi: `snake_case` kullan (örn: `work_table`, `tool_cabinet`)
- Boşluk ve Türkçe karakter kullanma
- Mesh dosyası model ismiyle aynı olmalı

### Mesh Optimizasyonu

1. **Polygon sayısını düşük tut**
   - Görsel mesh: Max 50,000 polygon
   - Collision mesh: Max 5,000 polygon (veya basit geometri)

2. **Gereksiz detayları kaldır**
   - İç yüzeyler
   - Görünmeyen parçalar
   - Çok küçük detaylar

3. **Modifiers uygula**
   - Export öncesi tüm modifiers'ı apply et
   - Armature kullanma (statik modeller için)

---

## Blender Export Adımları

### Adım 1: Model Hazırlığı

```
1. Object Mode'a geç
2. Tüm objeleri seç (A)
3. Apply → All Transforms (Ctrl+A)
4. Origin'i ayarla: Object → Set Origin → Origin to Geometry
```

### Adım 2: COLLADA Export

```
File → Export → Collada (.dae)
```

**Export Ayarları:**

| Ayar | Değer |
|------|-------|
| Selection Only | ✓ (seçili objeleri export et) |
| Include Children | ✓ |
| Include Armatures | ✗ |
| Include Shape Keys | ✗ |
| Apply Modifiers | ✓ (View settings) |
| Global Orientation | Forward: -Y, Up: Z |
| Apply Global Orientation | ✓ |
| Triangulate | ✓ |

### Adım 3: Texture Export (Opsiyonel)

Eğer texture kullanıyorsan:

```
1. Texture dosyalarını meshes/ klasörüne kopyala
2. Veya materials/textures/ klasörüne koy
3. model.sdf'de texture path'ini güncelle
```

---

## Gazebo Model Dosyaları

### model.config Şablonu

```xml
<?xml version="1.0"?>
<model>
  <name>MODEL_NAME</name>
  <version>1.0</version>
  <sdf version="1.6">model.sdf</sdf>
  
  <author>
    <name>YOUR_NAME</name>
    <email>your@email.com</email>
  </author>
  
  <description>
    Model açıklaması.
  </description>
</model>
```

### model.sdf Şablonu

```xml
<?xml version="1.0"?>
<sdf version="1.6">
  <model name="MODEL_NAME">
    <static>true</static>
    
    <link name="MODEL_NAME_link">
      <!-- Görsel -->
      <visual name="MODEL_NAME_visual">
        <pose>0 0 0 0 0 0</pose>
        <geometry>
          <mesh>
            <uri>model://MODEL_NAME/meshes/MODEL_NAME.dae</uri>
            <scale>1 1 1</scale>
          </mesh>
        </geometry>
      </visual>
      
      <!-- Çarpışma -->
      <collision name="MODEL_NAME_collision">
        <pose>0 0 0 0 0 0</pose>
        <geometry>
          <!-- Seçenek 1: Aynı mesh -->
          <mesh>
            <uri>model://MODEL_NAME/meshes/MODEL_NAME.dae</uri>
          </mesh>
          
          <!-- Seçenek 2: Basit geometri (daha performanslı)
          <box>
            <size>WIDTH HEIGHT DEPTH</size>
          </box>
          -->
        </geometry>
      </collision>
    </link>
  </model>
</sdf>
```

---

## Proje Klasör Yapısı

```
src/digital_twin_environment/
├── models/
│   ├── workbench/           ← Çalışma masası (xArm 5 monte)
│   │   ├── model.config
│   │   ├── model.sdf
│   │   └── meshes/
│   │       └── workbench.dae
│   ├── lab_floor/           ← Laboratuvar zemini
│   │   ├── model.config
│   │   ├── model.sdf
│   │   └── meshes/
│   │       └── lab_floor.dae
│   └── [yeni_model]/        ← Yeni modeller buraya
│       ├── model.config
│       ├── model.sdf
│       └── meshes/
│           └── [yeni_model].dae
└── worlds/
    └── robotics_lab.world   ← Ana world dosyası
```

---

## World Dosyasına Model Ekleme

`robotics_lab.world` dosyasına yeni model eklemek için:

```xml
<include>
  <uri>model://MODEL_NAME</uri>
  <name>instance_name</name>
  <pose>X Y Z ROLL PITCH YAW</pose>
</include>
```

**Pose formatı:**
- `X Y Z`: Pozisyon (metre)
- `ROLL PITCH YAW`: Rotasyon (radyan)

**Örnek:**
```xml
<!-- Raf - duvarın yanına yerleştir -->
<include>
  <uri>model://shelf</uri>
  <name>equipment_shelf_1</name>
  <pose>2.0 0.5 0 0 0 1.57</pose>  <!-- 90 derece dönük -->
</include>
```

---

## Model Ekleme Workflow

### Yeni Model Eklerken:

1. **Blender'da model oluştur** (yukarıdaki kurallara göre)

2. **Export et:**
   ```
   File → Export → Collada (.dae)
   Kaydet: src/digital_twin_environment/models/[model_name]/meshes/[model_name].dae
   ```

3. **model.config oluştur:**
   ```bash
   cp src/digital_twin_environment/models/workbench/model.config \
      src/digital_twin_environment/models/[model_name]/model.config
   # İçeriği düzenle
   ```

4. **model.sdf oluştur:**
   ```bash
   cp src/digital_twin_environment/models/workbench/model.sdf \
      src/digital_twin_environment/models/[model_name]/model.sdf
   # İçeriği düzenle
   ```

5. **World dosyasına ekle:**
   `worlds/robotics_lab.world` dosyasını aç ve `<include>` bloğu ekle

6. **Build ve test:**
   ```bash
   cd ~/Desktop/Digital-Twin
   colcon build --symlink-install --packages-select digital_twin_environment
   source install/setup.bash
   ros2 launch digital_twin_environment lab_with_xarm5.launch.py
   ```

---

## Collision Mesh Stratejileri

### 1. Aynı Mesh Kullan (Kolay)
```xml
<collision>
  <geometry>
    <mesh><uri>model://name/meshes/name.dae</uri></mesh>
  </geometry>
</collision>
```
- Avantaj: Doğru çarpışma
- Dezavantaj: Yavaş simülasyon

### 2. Basit Geometri (Performanslı)
```xml
<collision>
  <geometry>
    <box><size>1.0 0.5 0.8</size></box>
  </geometry>
</collision>
```
- Avantaj: Hızlı simülasyon
- Dezavantaj: Yaklaşık çarpışma

### 3. Simplified Mesh (Dengeli)
Blender'da ayrı bir low-poly collision mesh oluştur:
```xml
<collision>
  <geometry>
    <mesh><uri>model://name/meshes/name_collision.dae</uri></mesh>
  </geometry>
</collision>
```

---

## Troubleshooting

### Model görünmüyor
- `GAZEBO_MODEL_PATH` doğru ayarlanmış mı?
- `model://` URI'si doğru mu?
- Mesh dosyası doğru klasörde mi?

### Mesh ters görünüyor
- Blender'da normals'ı flip et: Edit Mode → Mesh → Normals → Flip

### Ölçek yanlış
- Blender'da unit scale kontrol et
- Export'ta scale ayarını kontrol et
- model.sdf'de `<scale>` değerini ayarla

### Texture yüklenmiyor
- Texture path'i relative olmalı
- Desteklenen formatlar: PNG, JPG, TGA

---

## Faydalı Blender Add-ons

- **Measure It**: Ölçüm için
- **Bool Tool**: Boolean operasyonlar
- **LoopTools**: Mesh düzenleme
- **Export Paper Model**: Düz yüzeyler için

---

## Sonraki Adımlar

1. Laboratuvar ortamını Blender'da modelleyin
2. Her eleman için ayrı model oluşturun
3. Bu rehberi takip ederek export edin
4. `robotics_lab.world` dosyasına ekleyin
5. Test edin ve pozisyonları ayarlayın

