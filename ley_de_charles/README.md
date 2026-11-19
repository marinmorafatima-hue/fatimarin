# LA LEY DE CHARLES — Vídeo educativo de animación de pizarra blanca

Proyecto completo para crear un vídeo educativo de **≈ 6 minutos, 1920×1080, 30 fps**
sobre la Ley de Charles, destinado a estudiantes de secundaria, con estilo
**whiteboard animation** (dibujo progresivo sobre pizarra blanca, sin narración incluida,
espacio para 3 voces).

## Contenido del proyecto

| Archivo / carpeta | Qué es |
|---|---|
| `videos/ley_de_charles_1080p.mp4` | **Vídeo final completo** (6:00, escenas ya unidas) |
| `videos/escena1.mp4 … escena7.mp4` | Las 7 escenas por separado (por si se montan individualmente) |
| `storyboard.md` | Storyboard completo: tiempos, dibujos, animaciones y textos de cada escena |
| `guion_voces.md` | Guion redactado para los 3 participantes, con marcas de tiempo |
| `instrucciones_edicion.md` | Cómo unir, poner las voces y exportar con CapCut |
| `render/render.py` | Generador de la animación (Python + Pillow): cómo se creó todo |
| `render/previews/` | Fotogramas de control de calidad |

## Estructura del vídeo

1. **Escena 1 · 0:00–0:40** — Introducción: globo, recipiente, partículas, título y termómetro.
2. **Escena 2 · 0:40–1:40** — ¿Qué es la Ley de Charles? El recipiente crece al calentarse.
3. **Escena 3 · 1:40–2:40** — Comparación FRÍO vs CALIENTE (partículas lentas vs rápidas).
4. **Escena 4 · 2:40–3:30** — Fórmula V1/T1 = V2/T2 y conversión K = °C + 273,15.
5. **Escena 5 · 3:30–4:15** — Ejemplo resuelto: V2 = (2 × 450)/300 = 3 litros.
6. **Escena 6 · 4:15–5:25** — Experimento de la botella y el globo (agua caliente / hielo).
7. **Escena 7 · 5:25–6:00** — Conclusión y frase clave final.

## Cómo regenerar las animaciones (opcional)

```bash
pip install pillow numpy imageio-ffmpeg matplotlib font-amatic-sc font-fredoka-one
python3 render.py todo          # todas las escenas + comprobación
python3 render.py escena 3      # solo la escena 3
python3 render.py preview 2 600 # PNG de la escena 2 en el segundo 20
```

Las escenas se renderizan en `videos/`. Para volver a unirlas:

```bash
ffmpeg -f concat -safe 0 -i <(for i in 1 2 3 4 5 6 7; do echo "file '$PWD/videos/escena$i.mp4'"; done) \
  -c copy videos/ley_de_charles_1080p.mp4
```
