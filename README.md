# Academic Report Pro 🎓

Generador de informes académicos con IA usando Flask + ReportLab + Llama 4 Scout.

## Estructura del proyecto

```
academic-report-pro/
├── app.py                  # Backend Flask completo
├── requirements.txt        # Dependencias Python
├── render.yaml             # Configuración Render
└── templates/
    └── index.html          # Frontend completo
```

## Funcionalidades

- **3 modos**: Rápido (solo tema), Automático (pega texto), Manual (escribe secciones)
- **4 tipos de informe**: Académico general, Laboratorio, Ejecutivo, Tesis
- **8 normas**: APA 7, APA 6, ICONTEC, Vancouver, Chicago, Harvard, MLA, IEEE
- **3 modos de referencias**: Automático (IA), Manual, Mixto
- **Múltiples autores** con botón "Agregar"
- **Fecha personalizable** con input date
- **Previsualización** del contenido IA antes de generar PDF
- **PDF profesional** con portada, índice, encabezado/pie por página

## Deploy en Render (Plan Gratuito)

### 1. Subir a GitHub

```bash
git init
git add .
git commit -m "Academic Report Pro v1.0"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/academic-report-pro.git
git push -u origin main
```

### 2. Crear servicio en Render

1. Ve a [render.com](https://render.com) → **New → Web Service**
2. Conecta tu repo de GitHub
3. Configuración:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 2`
   - **Environment**: Python 3

### 3. Variables de entorno

En Render → **Environment → Add Environment Variable**:

| Key | Value |
|-----|-------|
| `OPENROUTER_API_KEY` | Tu API key de OpenRouter |
| `FLASK_DEBUG` | `false` |

### 4. Obtener API Key de OpenRouter

1. Ve a [openrouter.ai](https://openrouter.ai)
2. Regístrate / inicia sesión
3. **Keys → Create Key**
4. Copia la key y pégala en Render

## Desarrollo local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno
export OPENROUTER_API_KEY="sk-or-..."

# Ejecutar
python app.py
# Abre http://localhost:5000
```

## Rutas API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Frontend principal |
| POST | `/generar` | Genera y descarga el PDF |
| POST | `/preview` | Retorna contenido IA (JSON) |
| GET | `/health` | Estado del servicio |

## Correcciones implementadas

- ✅ "INFORMÉ" → "INFORME"
- ✅ "Conclusions" → "CONCLUSIONES"
- ✅ Eliminación de caracteres no imprimibles con `re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', texto)`
- ✅ Timeout de 120s para generación IA
- ✅ Modelo `meta-llama/llama-4-scout` via OpenRouter
