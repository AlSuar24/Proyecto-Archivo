import io
import os
import re
import shutil
import tempfile
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import unicodedata

import cv2
import numpy as np
from PIL import Image, ImageStat, ImageTk
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
import pytesseract
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

CLAVE_POR_DEFECTO = "archivo2025"
CARATULA_BASE_NOMBRE = "CARATULA BASE OFICIAL.pdf"
CARPETA_DATASET = "dataset_sellos"
CARPETA_DATASET_DOCS = "dataset_documentos"

os.makedirs(CARPETA_DATASET, exist_ok=True)
os.makedirs(CARPETA_DATASET_DOCS, exist_ok=True)

RUTAS_TESSERACT = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
]
for ruta_t in RUTAS_TESSERACT:
    if os.path.exists(ruta_t):
        pytesseract.pytesseract.tesseract_cmd = ruta_t
        break


# ==============================================================================
# CONFIGURACIÓN DE TIPOS DOCUMENTALES (MÓDULOS 5 Y 6)
# ==============================================================================
TIPOS_DOCUMENTALES = [
    "Sin clasificar",
    "Valuación Inmobiliaria",
    "Certificado de puerta",
    "Deslinde y amojonamiento",
    "Boleto compra venta",
    "Escritura",
    "CA D1",
    "Plano de Arquitectura",
    "Expediente de obras"
]


# ==============================================================================
# UTILIDADES GENERALES Y DETECCIÓN DE SELLOS
# ==============================================================================

def es_pagina_en_blanco_visual(pdf_path: str, num_pag: int, umbral_brillo: float = 250.0) -> bool:
    try:
        doc = pdfium.PdfDocument(pdf_path, password=CLAVE_POR_DEFECTO)
        page = doc.get_page(num_pag)
        bitmap = page.render(scale=0.5)
        pil_image = bitmap.to_pil().convert("L")
        stat = ImageStat.Stat(pil_image)
        if stat.mean[0] >= umbral_brillo and stat.stddev[0] < 8.0:
            return True
        return False
    except Exception:
        return False


def extraer_todos_los_sellos_de_grilla(pdf_path: str, num_pag: int, password: str = CLAVE_POR_DEFECTO):
    recortes_encontrados = []
    try:
        try:
            doc = pdfium.PdfDocument(pdf_path, password=password)
        except Exception:
            doc = pdfium.PdfDocument(pdf_path)

        page = doc.get_page(num_pag)
        bitmap = page.render(scale=2.0)
        img_pil = bitmap.to_pil().convert("RGB")
        img_cv = np.array(img_pil)
        h_img, w_img, _ = img_cv.shape

        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
        
        kernel_lineas = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        gray_sin_lineas = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel_lineas)
        gray_blur = cv2.GaussianBlur(gray_sin_lineas, (7, 7), 0)

        hsv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2HSV)
        mascara_azul = cv2.inRange(hsv, np.array([85, 30, 25]), np.array([145, 255, 255]))

        candidatos_boxes = []
        circulos = cv2.HoughCircles(
            gray_blur, cv2.HOUGH_GRADIENT, dp=1.1, minDist=100,
            param1=50, param2=35, minRadius=65, maxRadius=130
        )

        if circulos is not None:
            for c in circulos[0]:
                cx, cy, r = int(round(c[0])), int(round(c[1])), int(round(c[2]))
                margen = int(r * 1.05)
                x1, y1 = max(0, cx - margen), max(0, cy - margen)
                x2, y2 = min(w_img, cx + margen), min(h_img, cy + margen)
                
                ancho_box = x2 - x1
                alto_box = y2 - y1
                if 120 < ancho_box < 280 and 120 < alto_box < 280:
                    zona_azul = mascara_azul[y1:y2, x1:x2]
                    if cv2.countNonZero(zona_azul) > 20:
                        candidatos_boxes.append((x1, y1, x2, y2, cy, cx))

        boxes_limpios = []
        for b in candidatos_boxes:
            x1, y1, x2, y2, cy, cx = b
            r = (x2 - x1) / 2
            solapado = False
            for bl in boxes_limpios:
                dist = np.hypot(cx - bl[5], cy - bl[4])
                if dist < r:
                    solapado = True
                    break
            if not solapado:
                boxes_limpios.append(b)

        boxes_limpios.sort(key=lambda b: (b[4] // 100, b[5]))
        for (x1, y1, x2, y2, _, _) in boxes_limpios:
            recorte_sello = Image.fromarray(img_cv[y1:y2, x1:x2])
            recortes_encontrados.append(recorte_sello)
    except Exception:
        pass
    return recortes_encontrados


def extraer_recorte_sello_individual(pdf_path: str, num_pag: int, password: str = CLAVE_POR_DEFECTO):
    try:
        try:
            doc = pdfium.PdfDocument(pdf_path, password=password)
        except Exception:
            doc = pdfium.PdfDocument(pdf_path)

        page = doc.get_page(num_pag)
        bitmap = page.render(scale=2.0)
        img_pil = bitmap.to_pil().convert("RGB")
        w, h = img_pil.size

        es_plano = w > (h * 1.15)
        if es_plano:
            x1_q, y1_q, x2_q, y2_q = int(w * 0.50), 0, w, int(h * 0.50)
        else:
            x1_q, y1_q, x2_q, y2_q = int(w * 0.40), 0, w, int(h * 0.50)

        cuadrante_pil = img_pil.crop((x1_q, y1_q, x2_q, y2_q))
        img_cv = np.array(cuadrante_pil)
        h_cv, w_cv, _ = img_cv.shape

        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
        gray_blur = cv2.GaussianBlur(gray, (7, 7), 0)
        
        circulos = cv2.HoughCircles(
            gray_blur, cv2.HOUGH_GRADIENT, dp=1.1, minDist=100,
            param1=50, param2=30, minRadius=50, maxRadius=150
        )

        recorte_sello = None
        if circulos is not None:
            for c in circulos[0]:
                cx, cy, r = int(round(c[0])), int(round(c[1])), int(round(c[2]))
                margen = int(r * 1.05)
                
                sx1, sy1 = max(0, cx - margen), max(0, cy - margen)
                sx2, sy2 = min(w_cv, cx + margen), min(h_cv, cy + margen)
                
                if (sx2 - sx1) > 60 and (sy2 - sy1) > 60:
                    recorte_temp = cuadrante_pil.crop((sx1, sy1, sx2, sy2))
                    rec_cv = np.array(recorte_temp.convert("RGB"))
                    hsv = cv2.cvtColor(rec_cv, cv2.COLOR_RGB2HSV)
                    mask_azul = cv2.inRange(hsv, np.array([85, 30, 25]), np.array([145, 255, 255]))
                    
                    if cv2.countNonZero(mask_azul) > 15:
                        try:
                            texto_sello = pytesseract.image_to_string(recorte_temp, config='--psm 6').lower()
                            if "folio" in texto_sello or "muni" in texto_sello or "gran" in texto_sello or "rio" in texto_sello:
                                recorte_sello = recorte_temp
                                break
                        except Exception:
                            recorte_sello = recorte_temp 
                            break

        return recorte_sello, img_pil
    except Exception:
        return None, None


def aislar_numero_birome(img_pil):
    img_cv = np.array(img_pil.convert("RGB"))
    hsv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2HSV)
    mask_azul = cv2.inRange(hsv, np.array([85, 30, 25]), np.array([145, 255, 255]))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    mask_limpia = cv2.morphologyEx(mask_azul, cv2.MORPH_OPEN, kernel)
    
    coords = cv2.findNonZero(mask_limpia)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        if w > 4 and h > 4:
            return mask_limpia[y:y+h, x:x+w]
    return None


def reconocer_por_base_conocimiento(recorte_pil):
    if not os.path.exists(CARPETA_DATASET): return None
    archivos = [f for f in os.listdir(CARPETA_DATASET) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not archivos: return None

    try:
        num_q = aislar_numero_birome(recorte_pil)
        if num_q is None: return None
        h_q, w_q = num_q.shape

        mejor_num, max_similitud = None, -1.0

        for arch in archivos:
            m = re.search(r"folio_(\d+)", arch)
            if not m: continue
            num_f = int(m.group(1))

            path_ej = os.path.join(CARPETA_DATASET, arch)
            try:
                img_ej = Image.open(path_ej)
                num_ej = aislar_numero_birome(img_ej)
                if num_ej is None: continue
                
                num_ej_res = cv2.resize(num_ej, (w_q, h_q))
                res = cv2.matchTemplate(num_q, num_ej_res, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)

                if max_val > max_similitud:
                    max_similitud = max_val
                    mejor_num = num_f
            except Exception:
                pass

        if max_similitud >= 0.60:
            return mejor_num
    except Exception:
        pass
    return None


def reconocer_documento_visual(img_pil):
    """Compara visualmente la hoja contra el dataset de documentos guardados (Módulo 6)."""
    if not os.path.exists(CARPETA_DATASET_DOCS): return None
    archivos = [f for f in os.listdir(CARPETA_DATASET_DOCS) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not archivos: return None
    
    img_cv = cv2.cvtColor(np.array(img_pil.convert("RGB")), cv2.COLOR_RGB2GRAY)
    mejor_tipo, max_sim = None, -1.0
    
    for arch in archivos:
        try:
            # El formato guardado es "INDICE_TIMESTAMP.png"
            idx_str = arch.split('_')[0]
            if not idx_str.isdigit(): continue
            idx_tipo = int(idx_str)
            if idx_tipo >= len(TIPOS_DOCUMENTALES): continue
            
            tipo_oficial = TIPOS_DOCUMENTALES[idx_tipo]
            path_ej = os.path.join(CARPETA_DATASET_DOCS, arch)
            
            img_ej = cv2.imread(path_ej, cv2.IMREAD_GRAYSCALE)
            if img_ej is None: continue
            
            h_ej, w_ej = img_ej.shape
            if h_ej > img_cv.shape[0] or w_ej > img_cv.shape[1]: continue
                
            res = cv2.matchTemplate(img_cv, img_ej, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            
            if max_val > max_sim:
                max_sim = max_val
                mejor_tipo = tipo_oficial
        except:
            pass
            
    # Umbral de similitud del 75% para considerar que es el mismo encabezado
    if max_sim >= 0.75:
        return mejor_tipo
    return None


# ==============================================================================
# MÓDULO 1: UNIFICACIÓN DE LEGAJO
# ==============================================================================

def modulo_unificacion_legajo(root):
    entrada_usuario = simpledialog.askstring("Número de Legajo", "Ingrese el número de legajo:", parent=root)
    if not entrada_usuario or not entrada_usuario.strip(): return
    num_puro = entrada_usuario.strip().rstrip("/")
    if num_puro.endswith("/00"): num_puro = num_puro[:-3]
    legajo_caratula = f"{num_puro}/00"

    ruta_caratula = os.path.join(os.getcwd(), CARATULA_BASE_NOMBRE)
    if not os.path.exists(ruta_caratula):
        ruta_caratula = filedialog.askopenfilename(title=f"Seleccionar {CARATULA_BASE_NOMBRE}", filetypes=[("Archivos PDF", "*.pdf")])
        if not ruta_caratula: return

    try:
        lector_base = PdfReader(ruta_caratula)
        if lector_base.is_encrypted: lector_base.decrypt(CLAVE_POR_DEFECTO)
        pagina_base = lector_base.pages[0]
        ancho, alto = float(pagina_base.mediabox.width), float(pagina_base.mediabox.height)
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(ancho, alto))
        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", 24)
        c.drawString(ancho * 0.315, alto * 0.468, legajo_caratula)
        c.save()
        buffer.seek(0)
        pagina_base.merge_page(PdfReader(buffer).pages[0])
        writer_final = PdfWriter()
        writer_final.add_page(pagina_base)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo generar la carátula: {str(e)}")
        return

    es_primera = True
    while True:
        if not es_primera and not messagebox.askyesno("Agregar", "¿Desea agregar más archivos PDF?"): break
        archivos = filedialog.askopenfilenames(title="Seleccionar archivos PDF", filetypes=[("Archivos PDF", "*.pdf")])
        if not archivos:
            if es_primera and not messagebox.askyesno("Vacío", "¿Continuar solo con carátula?"): return
            break
        for archivo in archivos:
            try:
                lector = PdfReader(archivo)
                if lector.is_encrypted and lector.decrypt(CLAVE_POR_DEFECTO) == 0:
                    clave = simpledialog.askstring("Clave", f"Ingrese clave para '{os.path.basename(archivo)}':", parent=root)
                    if clave: lector.decrypt(clave)
                for idx in range(len(lector.pages)):
                    if not es_pagina_en_blanco_visual(archivo, idx):
                        writer_final.add_page(lector.pages[idx])
            except Exception as e:
                messagebox.showerror("Error", f"Error en '{os.path.basename(archivo)}':\n{str(e)}")
        es_primera = False

    ruta_g = filedialog.asksaveasfilename(
        title="Guardar como...", initialfile=f"LEGAJO {num_puro}.pdf",
        defaultextension=".pdf", filetypes=[("Archivos PDF", "*.pdf")], parent=root
    )
    if ruta_g:
        with open(ruta_g, "wb") as f: writer_final.write(f)
        messagebox.showinfo("Éxito", f"Guardado en:\n{ruta_g}")


# ==============================================================================
# MÓDULO 2: CONTRASEÑAS
# ==============================================================================

def modulo_gestion_contrasenas(root):
    eleccion = {"accion": None}
    win = tk.Toplevel(root)
    win.title("Contraseñas")
    win.geometry("360x170")
    win.attributes("-topmost", True)
    
    def set_acc(a):
        eleccion["accion"] = a
        win.destroy()

    tk.Label(win, text="GESTIÓN DE CONTRASEÑAS", font=("Helvetica", 11, "bold"), pady=8).pack()
    tk.Button(win, text="Quitar Contraseña", bg="#c0392b", fg="white", command=lambda: set_acc("quitar")).pack(side="left", padx=20, pady=20)
    tk.Button(win, text="Agregar Contraseña", bg="#27ae60", fg="white", command=lambda: set_acc("agregar")).pack(side="right", padx=20, pady=20)
    win.wait_window()

    if not eleccion["accion"]: return
    carpeta = filedialog.askdirectory(title="Seleccionar carpeta")
    if not carpeta: return
    pdfs = [os.path.join(carpeta, f) for f in os.listdir(carpeta) if f.lower().endswith(".pdf")]

    for archivo in pdfs:
        try:
            lector = PdfReader(archivo)
            if lector.is_encrypted: lector.decrypt(CLAVE_POR_DEFECTO)
            writer = PdfWriter()
            for p in lector.pages: writer.add_page(p)
            if eleccion["accion"] == "agregar": writer.encrypt(CLAVE_POR_DEFECTO)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                temp_p = tmp.name
                writer.write(tmp)
            shutil.move(temp_p, archivo)
        except Exception:
            pass
    messagebox.showinfo("Finalizado", "Proceso completado con éxito.")


# ==============================================================================
# MÓDULO 4: ENTRENAMIENTO DE GRILLAS DE SELLOS
# ==============================================================================

def modulo_entrenamiento_base(root):
    archivo_pdf = filedialog.askopenfilename(title="Seleccionar PDF con Grilla de Sellos de Ejemplo", filetypes=[("Archivos PDF", "*.pdf")])
    if not archivo_pdf: return

    try:
        lector = PdfReader(archivo_pdf)
        password_usada = CLAVE_POR_DEFECTO
        if lector.is_encrypted and lector.decrypt(CLAVE_POR_DEFECTO) == 0:
            clave = simpledialog.askstring("Clave", "Ingrese clave del PDF:", parent=root)
            if clave:
                lector.decrypt(clave)
                password_usada = clave

        total_paginas = len(lector.pages)
        if total_paginas < 1: return

        progreso = tk.Toplevel(root)
        progreso.title("Analizando Grillas...")
        progreso.geometry("380x110")
        progreso.attributes("-topmost", True)
        tk.Label(progreso, text="Detectando sellos individuales válidos...", pady=10).pack()
        barra = ttk.Progressbar(progreso, length=300, mode="determinate", maximum=total_paginas)
        barra.pack(pady=5)
        progreso.update()

        todos_los_recortes = []
        for idx in range(total_paginas):
            recortes_pagina = extraer_todos_los_sellos_de_grilla(archivo_pdf, idx, password=password_usada)
            todos_los_recortes.extend(recortes_pagina)
            barra.step(1)
            progreso.update()
        progreso.destroy()

        if not todos_los_recortes:
            messagebox.showwarning("Sin resultados", "No se encontraron sellos con tinta azul de birome en este PDF.")
            return

        win_ent = tk.Toplevel(root)
        win_ent.title("Módulo 4: Entrenamiento de Base de Conocimiento")
        win_ent.geometry("640x580")
        win_ent.attributes("-topmost", True)
        ancho_p = win_ent.winfo_screenwidth()
        alto_p = win_ent.winfo_screenheight()
        x, y = (ancho_p // 2) - (640 // 2), (alto_p // 2) - (580 // 2)
        win_ent.geometry(f"+{x}+{y}")

        tk.Label(win_ent, text="ENTRENAMIENTO DE SELLOS", font=("Helvetica", 13, "bold"), pady=8).pack()
        tk.Label(win_ent, text="Indique el número real de cada sello extraído y presione Guardar.", font=("Helvetica", 9), fg="#333333").pack(pady=2)

        frame_centro = tk.Frame(win_ent, pady=10)
        frame_centro.pack(fill="both", expand=True, padx=20)
        lbl_info_sello = tk.Label(frame_centro, font=("Helvetica", 11, "bold"), fg="#2b5797")
        lbl_info_sello.pack(pady=5)
        lbl_img_sello = tk.Label(frame_centro, bg="#2f3542", bd=2, relief="groove")
        lbl_img_sello.pack(pady=10)
        frame_input = tk.Frame(frame_centro, pady=10)
        frame_input.pack()
        tk.Label(frame_input, text="Número de Folio Real:", font=("Helvetica", 11, "bold")).pack(side="left", padx=5)
        var_num_real = tk.StringVar()
        ent_num_real = tk.Entry(frame_input, textvariable=var_num_real, font=("Helvetica", 13, "bold"), width=8, justify="center")
        ent_num_real.pack(side="left", padx=5)

        estado_idx = {"actual": 0}
        img_tk_ref = [None]

        def mostrar_sello_actual():
            idx = estado_idx["actual"]
            if idx >= len(todos_los_recortes):
                messagebox.showinfo("Entrenamiento Finalizado", f"¡Se han guardado todos los sellos en la carpeta '{CARPETA_DATASET}'!")
                win_ent.destroy()
                return
            lbl_info_sello.config(text=f"Sello detectado {idx + 1} de {len(todos_los_recortes)}")
            var_num_real.set("")
            recorte = todos_los_recortes[idx]
            img_prev = recorte.copy()
            img_prev.thumbnail((340, 160))
            img_tk = ImageTk.PhotoImage(img_prev)
            img_tk_ref[0] = img_tk
            lbl_img_sello.config(image=img_tk, text="")
            ent_num_real.focus_set()

        def guardar_y_avanzar():
            val_txt = var_num_real.get().strip()
            if not val_txt.isdigit():
                messagebox.showwarning("Atención", "Ingrese un número entero válido.")
                return
            val_num = int(val_txt)
            recorte = todos_los_recortes[estado_idx["actual"]]
            if recorte is not None:
                timestamp_id = int(time.time() * 1000)
                path_ej = os.path.join(CARPETA_DATASET, f"folio_{val_num}_{timestamp_id}.png")
                recorte.save(path_ej)
            estado_idx["actual"] += 1
            mostrar_sello_actual()

        def saltar_sello():
            estado_idx["actual"] += 1
            mostrar_sello_actual()

        frame_btns = tk.Frame(win_ent, pady=15)
        frame_btns.pack()
        tk.Button(frame_btns, text="Omitir Sello", command=saltar_sello, font=("Helvetica", 10), padx=15, pady=6, cursor="hand2").pack(side="left", padx=10)
        tk.Button(frame_btns, text="Guardar y Siguiente ➔", bg="#27ae60", fg="white", font=("Helvetica", 10, "bold"), command=guardar_y_avanzar, padx=20, pady=6, cursor="hand2").pack(side="left", padx=10)
        ent_num_real.bind("<Return>", lambda e: guardar_y_avanzar())

        mostrar_sello_actual()
        win_ent.wait_window()
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error al procesar el archivo:\n{str(e)}")


# ==============================================================================
# MÓDULO 6: ENTRENAMIENTO VISUAL DE DOCUMENTOS (RECORTE LIBRE)
# ==============================================================================

class RecortadorDocumento:
    def __init__(self, master, img_pil):
        self.top = tk.Toplevel(master)
        self.top.title("Seleccionar Zona Clave del Documento")
        self.img_pil = img_pil
        
        w, h = img_pil.size
        self.scale = min(1000/w, 650/h, 1.0)
        nw, nh = int(w * self.scale), int(h * self.scale)
        self.img_resized = img_pil.resize((nw, nh), Image.Resampling.BILINEAR)
        self.tk_img = ImageTk.PhotoImage(self.img_resized)
        
        tk.Label(self.top, text="Dibuja un rectángulo sobre el título o formato que quieras que la IA reconozca siempre.", font=("Helvetica", 10)).pack(pady=5)
        
        self.canvas = tk.Canvas(self.top, width=nw, height=nh, cursor="cross")
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        
        self.rect = None
        self.start_x = None
        self.start_y = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        
        self.btn_frame = tk.Frame(self.top)
        self.btn_frame.pack(fill="x", pady=10)
        
        tk.Label(self.btn_frame, text="¿Qué documento es?", font=("Helvetica", 10, "bold")).pack(side="left", padx=10)
        self.var_tipo = tk.StringVar(value=TIPOS_DOCUMENTALES[1])
        self.cb = ttk.Combobox(self.btn_frame, textvariable=self.var_tipo, values=TIPOS_DOCUMENTALES, width=30)
        self.cb.pack(side="left", padx=5)
        
        tk.Button(self.btn_frame, text="✓ Guardar Patrón", bg="#00b894", fg="white", font=("Helvetica", 10, "bold"), command=self.guardar).pack(side="left", padx=15)
        tk.Button(self.btn_frame, text="Omitir Página", command=self.saltar).pack(side="left", padx=5)
        
        self.top.wait_window()
        
    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=3)
        
    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)
        
    def guardar(self):
        if not self.rect:
            messagebox.showwarning("Aviso", "Primero dibuja un rectángulo con el mouse.")
            return
        c = self.canvas.coords(self.rect)
        x1, y1, x2, y2 = [int(v / self.scale) for v in c]
        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])
        
        if (x2-x1) < 15 or (y2-y1) < 15:
            messagebox.showwarning("Aviso", "El área seleccionada es muy pequeña.")
            return
            
        recorte = self.img_pil.crop((x1, y1, x2, y2))
        tipo_seleccionado = self.var_tipo.get()
        
        if tipo_seleccionado not in TIPOS_DOCUMENTALES:
            TIPOS_DOCUMENTALES.append(tipo_seleccionado)
            
        idx_tipo = TIPOS_DOCUMENTALES.index(tipo_seleccionado)
        timestamp = int(time.time() * 1000)
        nombre_archivo = f"{idx_tipo}_{timestamp}.png"
        ruta = os.path.join(CARPETA_DATASET_DOCS, nombre_archivo)
        recorte.save(ruta)
        
        messagebox.showinfo("Guardado", f"Patrón visual de '{tipo_seleccionado}' guardado con éxito.")
        self.top.destroy()
        
    def saltar(self):
        self.top.destroy()


def modulo_entrenamiento_docs(root):
    archivo_pdf = filedialog.askopenfilename(title="Seleccionar PDF (Ejemplo de Documento)", filetypes=[("Archivos PDF", "*.pdf")])
    if not archivo_pdf: return
    try:
        lector = PdfReader(archivo_pdf)
        password_usada = CLAVE_POR_DEFECTO
        if lector.is_encrypted and lector.decrypt(CLAVE_POR_DEFECTO) == 0:
            clave = simpledialog.askstring("Clave", "Ingrese clave del PDF:", parent=root)
            if clave:
                lector.decrypt(clave)
                password_usada = clave
        
        total = len(lector.pages)
        for idx in range(total):
            doc = pdfium.PdfDocument(archivo_pdf, password=password_usada)
            page = doc.get_page(idx)
            bitmap = page.render(scale=2.0)
            img_pil = bitmap.to_pil().convert("RGB")
            
            # Abrir el recortador para esta hoja
            RecortadorDocumento(root, img_pil)
            
            if not messagebox.askyesno("Continuar", "¿Desea seguir entrenando con la siguiente página de este PDF?"):
                break
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error:\n{str(e)}")


# ==============================================================================
# MÓDULO 3: ORDENAR LEGAJO USANDO LA BASE DE CONOCIMIENTO LOCAL
# ==============================================================================

def ventana_visor_ampliado(root, img_pil, titulo):
    top = tk.Toplevel(root)
    top.title(f"Inspección - {titulo}")
    top.geometry("800x640")
    top.attributes("-topmost", True)
    top.transient(root)
    canvas = tk.Canvas(top, bg="#2f3542", cursor="fleur")
    canvas.pack(fill="both", expand=True)
    st = {"img": img_pil, "zoom": 0.65, "x": -120, "y": 0, "dx": 0, "dy": 0, "tk": None}

    def dib():
        if st["img"] is None: return
        w, h = st["img"].size
        nw, nh = max(50, int(w * st["zoom"])), max(50, int(h * st["zoom"]))
        res = st["img"].resize((nw, nh), Image.Resampling.BILINEAR)
        tk_img = ImageTk.PhotoImage(res)
        st["tk"] = tk_img
        canvas.delete("all")
        canvas.create_image(st["x"], st["y"], anchor="nw", image=tk_img)

    canvas.bind("<ButtonPress-1>", lambda e: st.update(dx=e.x, dy=e.y))
    canvas.bind("<B1-Motion>", lambda e: (st.update(x=st["x"] + e.x - st["dx"], y=st["y"] + e.y - st["dy"], dx=e.x, dy=e.y), dib()))
    canvas.bind("<MouseWheel>", lambda e: (st.update(zoom=min(3.0, st["zoom"] + 0.15) if e.delta > 0 else max(0.2, st["zoom"] - 0.15)), dib()))
    top.after(50, dib)


def ventana_gestor_orden(root, lista_paginas):
    ventana = tk.Toplevel(root)
    ventana.title("Gestor Visual Inteligente de Foliatura")
    ventana.geometry("1140x760")
    ventana.attributes("-topmost", True)
    ancho_p = ventana.winfo_screenwidth()
    alto_p = ventana.winfo_screenheight()
    x, y = (ancho_p // 2) - (1140 // 2), (alto_p // 2) - (760 // 2)
    ventana.geometry(f"+{x}+{y}")

    tk.Label(ventana, text="CONTROL Y RECONOCIMIENTO INTELIGENTE", font=("Helvetica", 13, "bold"), pady=4).pack()
    tk.Label(ventana, text="Los reversos no requieren entrada, heredan el número de su hoja frontal.\nUsa 'Tab' para revisar y presiona Enter para confirmar ordenamiento.", font=("Helvetica", 9), fg="#333333").pack(pady=2)

    frame_headers = tk.Frame(ventana, bg="#2b5797", height=32)
    frame_headers.pack(fill="x", padx=15, pady=(8, 0))
    tk.Label(frame_headers, text="Foto Sello Limpio", font=("Helvetica", 9, "bold"), bg="#2b5797", fg="white", width=28, anchor="center").pack(side="left", padx=5)
    tk.Label(frame_headers, text="Hoja PDF", font=("Helvetica", 9, "bold"), bg="#2b5797", fg="white", width=12, anchor="center").pack(side="left", padx=5)
    tk.Label(frame_headers, text="Tipo", font=("Helvetica", 9, "bold"), bg="#2b5797", fg="white", width=14, anchor="center").pack(side="left", padx=5)
    tk.Label(frame_headers, text="N° de Folio Real", font=("Helvetica", 9, "bold"), bg="#2b5797", fg="white", width=22, anchor="center").pack(side="left", padx=5)
    tk.Label(frame_headers, text="Ajuste Fino", font=("Helvetica", 9, "bold"), bg="#2b5797", fg="white", width=16, anchor="center").pack(side="left", padx=5)

    frame_scroll = tk.Frame(ventana)
    frame_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 6))
    canvas_scroll = tk.Canvas(frame_scroll, bg="#f5f6fa", highlightthickness=0)
    scrollbar = ttk.Scrollbar(frame_scroll, orient="vertical", command=canvas_scroll.yview)
    frame_filas = tk.Frame(canvas_scroll, bg="#f5f6fa")

    frame_filas.bind("<Configure>", lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
    ventana_canvas = canvas_scroll.create_window((0, 0), window=frame_filas, anchor="nw")
    canvas_scroll.bind("<Configure>", lambda e: canvas_scroll.itemconfig(ventana_canvas, width=e.width))
    canvas_scroll.configure(yscrollcommand=scrollbar.set)
    canvas_scroll.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    canvas_scroll.bind_all("<MouseWheel>", lambda e: canvas_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    fotos_tk = []
    lista_entries = []

    def reorganizar_y_renderizar():
        lista_paginas.sort(key=lambda x: (x["folio_asignado"], 1 if x["es_reverso"] else 0, x["num_pag"]))
        renderizar_filas()

    def renderizar_filas():
        fotos_tk.clear()
        lista_entries.clear()
        for w in frame_filas.winfo_children(): w.destroy()

        for idx, item in enumerate(lista_paginas):
            es_mod = item.get("corregido_manual", False)
            bg_color = "#eafaf1" if es_mod else ("#ffffff" if idx % 2 == 0 else "#f0f2f5")

            fila = tk.Frame(frame_filas, bg=bg_color, pady=4, padx=5, bd=1, relief="solid")
            fila.pack(fill="x", expand=True, padx=2, pady=2)

            recorte = item.get("recorte_sello")
            if recorte is not None:
                thumb = recorte.copy()
                thumb.thumbnail((240, 110))
                tk_img = ImageTk.PhotoImage(thumb)
                fotos_tk.append(tk_img)
                lbl_img = tk.Label(fila, image=tk_img, bg=bg_color, cursor="hand2", bd=1, relief="groove")
                lbl_img.pack(side="left", padx=10)
                lbl_img.bind("<Button-1>", lambda e, img=item.get("imagen_pagina"), p=item["num_pag"] + 1: ventana_visor_ampliado(ventana, img, f"Hoja {p}"))
            else:
                tk.Label(fila, text="[Reverso / Anexo]", width=22, bg=bg_color, fg="#888888").pack(side="left", padx=10)

            tk.Label(fila, text=f"Hoja PDF {item['num_pag'] + 1}", font=("Helvetica", 10, "bold"), bg=bg_color, width=12, anchor="center").pack(side="left", padx=4)

            tipo_txt = "Reverso" if item["es_reverso"] else "Frente"
            color_t = "#d35400" if item["es_reverso"] else "#27ae60"
            tk.Label(fila, text=tipo_txt, font=("Helvetica", 9, "bold"), fg=color_t, bg=bg_color, width=12, anchor="center").pack(side="left", padx=4)

            frame_ed = tk.Frame(fila, bg=bg_color)
            frame_ed.pack(side="left", padx=25)

            if item["es_reverso"]:
                tk.Label(frame_ed, text="---", font=("Helvetica", 12, "bold"), fg="#7f8c8d", bg="#ffffff", width=8).pack(side="left", padx=4)
                tk.Label(frame_ed, text="Se une al anterior", font=("Helvetica", 8, "italic"), fg="#7f8c8d", bg=bg_color).pack(side="left", padx=4)
            else:
                var_val = tk.StringVar(value=str(item["folio_asignado"]))
                ent_val = tk.Entry(frame_ed, textvariable=var_val, font=("Helvetica", 12, "bold"), width=8, justify="center", bg="#ffffff")
                ent_val.pack(side="left", padx=4)
                lista_entries.append(ent_val)

                def actualizar_folio(i=idx, v=var_val):
                    txt = v.get().strip()
                    if not txt.isdigit(): return
                    val_num = int(txt)
                    
                    lista_paginas[i]["folio_asignado"] = val_num
                    lista_paginas[i]["corregido_manual"] = True
                    
                    try:
                        rec = lista_paginas[i].get("recorte_sello")
                        if rec:
                            timestamp_id = int(time.time() * 1000)
                            path_ej = os.path.join(CARPETA_DATASET, f"folio_{val_num}_{timestamp_id}.png")
                            rec.save(path_ej)
                    except Exception: pass
                    
                    if i + 1 < len(lista_paginas) and lista_paginas[i + 1]["es_reverso"]:
                        lista_paginas[i + 1]["folio_asignado"] = val_num

                    reorganizar_y_renderizar()

                tk.Button(frame_ed, text="Ok", font=("Helvetica", 9, "bold"), bg="#0984e3", fg="white", padx=8, pady=2, command=actualizar_folio, cursor="hand2").pack(side="left", padx=4)
                ent_val.bind("<Return>", lambda e, f=actualizar_folio: f())

                def saltar_tab(e, current_idx=len(lista_entries)-1):
                    next_idx = current_idx + 1
                    if next_idx < len(lista_entries):
                        target_entry = lista_entries[next_idx]
                        target_entry.focus_set()
                        target_entry.select_range(0, tk.END)
                        total = len(lista_paginas)
                        fraccion = max(0.0, min(1.0, (next_idx - 2) / max(1, total)))
                        canvas_scroll.yview_moveto(fraccion)
                    return "break"
                ent_val.bind("<Tab>", saltar_tab)

            frame_sb = tk.Frame(fila, bg=bg_color)
            frame_sb.pack(side="left", padx=15)

            def subir(i=idx):
                if i > 0:
                    lista_paginas[i], lista_paginas[i - 1] = lista_paginas[i - 1], lista_paginas[i]
                    lista_paginas[i - 1]["corregido_manual"] = True
                    reorganizar_y_renderizar()
            def bajar(i=idx):
                if i < len(lista_paginas) - 1:
                    lista_paginas[i], lista_paginas[i + 1] = lista_paginas[i + 1], lista_paginas[i]
                    lista_paginas[i + 1]["corregido_manual"] = True
                    reorganizar_y_renderizar()

            tk.Button(frame_sb, text="▲", font=("Helvetica", 8, "bold"), width=3, command=subir, cursor="hand2").pack(side="left", padx=2)
            tk.Button(frame_sb, text="▼", font=("Helvetica", 8, "bold"), width=3, command=bajar, cursor="hand2").pack(side="left", padx=2)

    confirmado = {"ok": False}
    def confirmar():
        canvas_scroll.unbind_all("<MouseWheel>")
        confirmado["ok"] = True
        ventana.destroy()

    frame_inf = tk.Frame(ventana, pady=8)
    frame_inf.pack(fill="x", padx=15)
    tk.Button(frame_inf, text="Cancelar", command=lambda: (canvas_scroll.unbind_all("<MouseWheel>"), ventana.destroy()), padx=15, pady=6).pack(side="left", padx=5)
    tk.Button(frame_inf, text="✓ CONFIRMAR Y GUARDAR PDF ORDENADO", font=("Helvetica", 11, "bold"), bg="#00b894", fg="white", command=confirmar, padx=25, pady=6, cursor="hand2").pack(side="right", padx=5)

    reorganizar_y_renderizar()
    ventana.wait_window()
    return confirmado["ok"]


def modulo_ordenar_por_foliatura(root):
    archivo_pdf = filedialog.askopenfilename(title="Seleccionar Legajo Unificado", filetypes=[("Archivos PDF", "*.pdf")])
    if not archivo_pdf: return

    try:
        lector = PdfReader(archivo_pdf)
        password_usada = CLAVE_POR_DEFECTO
        if lector.is_encrypted and lector.decrypt(CLAVE_POR_DEFECTO) == 0:
            clave = simpledialog.askstring("Clave", "Ingrese clave del PDF:", parent=root)
            if clave:
                lector.decrypt(clave)
                password_usada = clave

        total_paginas = len(lector.pages)
        if total_paginas <= 2:
            messagebox.showinfo("Aviso", "El documento tiene muy pocas páginas.")
            return

        progreso = tk.Toplevel(root)
        progreso.title("Analizando...")
        progreso.geometry("400x120")
        progreso.attributes("-topmost", True)
        tk.Label(progreso, text="Consultando Base de Conocimiento local...", pady=10).pack()
        barra = ttk.Progressbar(progreso, length=320, mode="determinate", maximum=total_paginas - 1)
        barra.pack(pady=5)
        progreso.update()

        caratula = lector.pages[0]
        datos = []
        ultimo_folio_asig = 0

        for idx in range(1, total_paginas):
            recorte, img_entera = extraer_recorte_sello_individual(archivo_pdf, idx, password=password_usada)
            es_rev = (recorte is None)
            folio_reconocido = None

            if not es_rev:
                folio_reconocido = reconocer_por_base_conocimiento(recorte)
                if folio_reconocido is not None:
                    folio_asig = folio_reconocido
                else:
                    folio_asig = ultimo_folio_asig + 1
                ultimo_folio_asig = folio_asig
            else:
                folio_asig = ultimo_folio_asig

            datos.append({
                "num_pag": idx,
                "folio_asignado": folio_asig,
                "es_reverso": es_rev,
                "corregido_manual": (not es_rev and folio_reconocido is not None),
                "recorte_sello": recorte,
                "imagen_pagina": img_entera,
                "pagina_obj": lector.pages[idx]
            })
            barra.step(1)
            progreso.update()
        progreso.destroy()

        if not ventana_gestor_orden(root, datos): return

        writer = PdfWriter()
        writer.add_page(caratula)
        for item in datos: writer.add_page(item["pagina_obj"])

        dir_n, nom_n = os.path.split(archivo_pdf)
        base_n, ext_n = os.path.splitext(nom_n)
        ruta_salida = os.path.join(dir_n, f"{base_n}_ORDENADO{ext_n}")

        with open(ruta_salida, "wb") as f_out: writer.write(f_out)
        messagebox.showinfo("Éxito", f"Legajo ordenado correctamente en:\n{ruta_salida}")
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error:\n{str(e)}")


# ==============================================================================
# MÓDULO 5: CLASIFICACIÓN HÍBRIDA (VISIÓN + OCR EN CASCADA)
# ==============================================================================

def ventana_clasificador_marcadores(root, datos_paginas):
    ventana = tk.Toplevel(root)
    ventana.title("Clasificación Cronológica y Documental")
    ventana.geometry("1100x700")
    ventana.attributes("-topmost", True)
    ancho_p = ventana.winfo_screenwidth()
    alto_p = ventana.winfo_screenheight()
    x, y = (ancho_p // 2) - (1100 // 2), (alto_p // 2) - (700 // 2)
    ventana.geometry(f"+{x}+{y}")

    tk.Label(ventana, text="MÓDULO 5: CLASIFICACIÓN Y MARCADORES", font=("Helvetica", 13, "bold"), pady=4).pack()
    tk.Label(ventana, text="Revise el Año y Tipo Documental. Si deja el Año en blanco, hereda el de arriba.\nAl confirmar, se guardará el índice interactivo.", font=("Helvetica", 9), fg="#333333").pack(pady=2)

    frame_headers = tk.Frame(ventana, bg="#8e44ad", height=32)
    frame_headers.pack(fill="x", padx=15, pady=(8, 0))
    tk.Label(frame_headers, text="Miniatura de Hoja", font=("Helvetica", 9, "bold"), bg="#8e44ad", fg="white", width=22, anchor="center").pack(side="left", padx=5)
    tk.Label(frame_headers, text="N° Hoja", font=("Helvetica", 9, "bold"), bg="#8e44ad", fg="white", width=10, anchor="center").pack(side="left", padx=5)
    tk.Label(frame_headers, text="Año (En blanco = Hereda)", font=("Helvetica", 9, "bold"), bg="#8e44ad", fg="white", width=24, anchor="center").pack(side="left", padx=15)
    tk.Label(frame_headers, text="Tipo Documental", font=("Helvetica", 9, "bold"), bg="#8e44ad", fg="white", width=35, anchor="center").pack(side="left", padx=5)

    frame_scroll = tk.Frame(ventana)
    frame_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 6))
    canvas_scroll = tk.Canvas(frame_scroll, bg="#f5f6fa", highlightthickness=0)
    scrollbar = ttk.Scrollbar(frame_scroll, orient="vertical", command=canvas_scroll.yview)
    frame_filas = tk.Frame(canvas_scroll, bg="#f5f6fa")

    frame_filas.bind("<Configure>", lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
    ventana_canvas = canvas_scroll.create_window((0, 0), window=frame_filas, anchor="nw")
    canvas_scroll.bind("<Configure>", lambda e: canvas_scroll.itemconfig(ventana_canvas, width=e.width))
    canvas_scroll.configure(yscrollcommand=scrollbar.set)
    canvas_scroll.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    canvas_scroll.bind_all("<MouseWheel>", lambda e: canvas_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    for idx, item in enumerate(datos_paginas):
        bg_color = "#ffffff" if idx % 2 == 0 else "#f0f2f5"
        fila = tk.Frame(frame_filas, bg=bg_color, pady=4, padx=5, bd=1, relief="solid")
        fila.pack(fill="x", expand=True, padx=2, pady=2)

        img_pil = item["imagen"]
        if img_pil:
            thumb = img_pil.copy()
            thumb.thumbnail((180, 100))
            tk_img = ImageTk.PhotoImage(thumb)
            item["tk_img"] = tk_img 
            lbl_img = tk.Label(fila, image=tk_img, bg=bg_color, cursor="hand2", bd=1, relief="groove")
            lbl_img.pack(side="left", padx=10)
            lbl_img.bind("<Button-1>", lambda e, i=img_pil, p=item["num_pag"]: ventana_visor_ampliado(ventana, i, f"Hoja {p}"))
        else:
            tk.Label(fila, text="[Sin imagen]", width=22, bg=bg_color).pack(side="left", padx=10)

        tk.Label(fila, text=f"Pág {item['num_pag']}", font=("Helvetica", 10, "bold"), bg=bg_color, width=10, anchor="center").pack(side="left", padx=5)

        var_anio = tk.StringVar(value=item["anio"])
        item["var_anio"] = var_anio
        tk.Entry(fila, textvariable=var_anio, font=("Helvetica", 11, "bold"), width=12, justify="center").pack(side="left", padx=25)

        var_tipo = tk.StringVar(value=item["tipo"])
        item["var_tipo"] = var_tipo
        ttk.Combobox(fila, textvariable=var_tipo, values=TIPOS_DOCUMENTALES, font=("Helvetica", 11), width=35).pack(side="left", padx=15)

    confirmado = {"ok": False}
    def confirmar():
        for item in datos_paginas:
            item["anio"] = item["var_anio"].get().strip()
            item["tipo"] = item["var_tipo"].get().strip()
            # Si escriben algo nuevo, agregarlo a la memoria
            if item["tipo"] not in TIPOS_DOCUMENTALES and item["tipo"] != "":
                TIPOS_DOCUMENTALES.append(item["tipo"])
        canvas_scroll.unbind_all("<MouseWheel>")
        confirmado["ok"] = True
        ventana.destroy()

    frame_inf = tk.Frame(ventana, pady=8)
    frame_inf.pack(fill="x", padx=15)
    tk.Button(frame_inf, text="Cancelar", command=lambda: (canvas_scroll.unbind_all("<MouseWheel>"), ventana.destroy()), padx=15, pady=6).pack(side="left", padx=5)
    tk.Button(frame_inf, text="✓ GENERAR PDF CON MARCADORES", font=("Helvetica", 11, "bold"), bg="#00b894", fg="white", command=confirmar, padx=25, pady=6, cursor="hand2").pack(side="right", padx=5)

    ventana.wait_window()
    return confirmado["ok"]


def modulo_clasificacion_marcadores(root):
    archivo_pdf = filedialog.askopenfilename(title="Seleccionar PDF (Legajo ya Ordenado)", filetypes=[("Archivos PDF", "*.pdf")])
    if not archivo_pdf: return

    try:
        lector = PdfReader(archivo_pdf)
        password_usada = CLAVE_POR_DEFECTO
        if lector.is_encrypted and lector.decrypt(CLAVE_POR_DEFECTO) == 0:
            clave = simpledialog.askstring("Clave", "Ingrese clave del PDF:", parent=root)
            if clave:
                lector.decrypt(clave)
                password_usada = clave

        total_paginas = len(lector.pages)
        if total_paginas < 1: return

        progreso = tk.Toplevel(root)
        progreso.title("Lectura y Reconocimiento")
        progreso.geometry("450x130")
        progreso.attributes("-topmost", True)
        tk.Label(progreso, text="Identificando documentos (Visión + OCR)...", pady=10).pack()
        barra = ttk.Progressbar(progreso, length=380, mode="determinate", maximum=total_paginas)
        barra.pack(pady=5)
        progreso.update()

        datos_analizados = []
        patron_anio = re.compile(r'\b(19[7-9]\d|20[0-3]\d)\b')
        ultimo_error_ocr = None

        diccionario_claves = {
            "valuacion": "Valuación Inmobiliaria",
            "inmobiliari": "Valuación Inmobiliaria",
            "certificado de puerta": "Certificado de puerta",
            "amojonamiento": "Deslinde y amojonamiento",
            "deslinde": "Deslinde y amojonamiento",
            "boleto de compra": "Boleto compra venta",
            "compraventa": "Boleto compra venta",
            "escritura": "Escritura",
            "ca d1": "CA D1",
            "cad 1": "CA D1",
            "arquitectura": "Plano de Arquitectura",
            "expediente de obra": "Expediente de obras"
        }

        for idx in range(total_paginas):
            try:
                doc = pdfium.PdfDocument(archivo_pdf, password=password_usada)
                page = doc.get_page(idx)
                bitmap = page.render(scale=2.0)
                img_pil_color = bitmap.to_pil().convert("RGB")
                img_pil = img_pil_color.convert("L")
                
                # 1. BÚSQUEDA VISUAL (Módulo 6) - CEREBRO 1
                tipo_detectado = reconocer_documento_visual(img_pil_color)
                
                # 2. OCR PARA FECHAS Y RESPALDO TEXTUAL - CEREBRO 2
                try:
                    texto_crudo = pytesseract.image_to_string(img_pil, lang='spa', config='--psm 3').lower()
                except Exception:
                    texto_crudo = pytesseract.image_to_string(img_pil, config='--psm 3').lower()
                
                texto_norm = unicodedata.normalize('NFKD', texto_crudo).encode('ASCII', 'ignore').decode('utf-8')
                texto_norm = re.sub(r'\s+', ' ', texto_norm)
                
                anios_encontrados = patron_anio.findall(texto_norm)
                anio_detectado = "" 
                if anios_encontrados:
                    anio_detectado = max(anios_encontrados)
                
                # Si la visión visual falló, buscar por texto
                if not tipo_detectado:
                    tipo_detectado = "Sin clasificar"
                    for clave_busqueda, tipo_oficial in diccionario_claves.items():
                        if clave_busqueda in texto_norm:
                            tipo_detectado = tipo_oficial
                            break

                datos_analizados.append({
                    "num_pag": idx + 1,
                    "imagen": img_pil_color,
                    "pagina_obj": lector.pages[idx],
                    "anio": anio_detectado,
                    "tipo": tipo_detectado
                })
            except Exception as e:
                ultimo_error_ocr = str(e)
                pass
            
            barra.step(1)
            progreso.update()

        progreso.destroy()

        if not datos_analizados:
            mensaje_falla = f"Error al procesar.\n\nCausa probable: OCR falló (Tesseract). Detalle: {ultimo_error_ocr}"
            messagebox.showwarning("Error Crítico", mensaje_falla)
            return

        if not ventana_clasificador_marcadores(root, datos_analizados): return

        writer = PdfWriter()
        for item in datos_analizados: writer.add_page(item["pagina_obj"])

        referencias_anios = {}
        anio_actual_cascada = "Sin Año / Otros"

        for item in datos_analizados:
            anio_ui = item["anio"]
            if anio_ui and anio_ui.lower() != "sin año" and anio_ui != "---":
                anio_actual_cascada = anio_ui
            
            if anio_actual_cascada not in referencias_anios:
                pagina_idx = item["num_pag"] - 1
                padre_obj = writer.add_outline_item(str(anio_actual_cascada), pagina_idx)
                referencias_anios[anio_actual_cascada] = padre_obj

            tipo = item["tipo"]
            if tipo and tipo != "Sin clasificar":
                pagina_idx = item["num_pag"] - 1
                titulo_marcador = f"{tipo} (Pág {item['num_pag']})"
                writer.add_outline_item(titulo_marcador, pagina_idx, parent=referencias_anios[anio_actual_cascada])

        dir_n, nom_n = os.path.split(archivo_pdf)
        base_n, ext_n = os.path.splitext(nom_n)
        ruta_salida = os.path.join(dir_n, f"{base_n}_INDEXADO{ext_n}")

        with open(ruta_salida, "wb") as f_out: writer.write(f_out)
        messagebox.showinfo("Éxito", f"Legajo indexado guardado en:\n{ruta_salida}")

    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error general:\n{str(e)}")


# ==============================================================================
# MENÚ PRINCIPAL
# ==============================================================================

def menu_principal():
    root = tk.Tk()
    root.title("Gestor Integral de Expedientes PDF")
    root.geometry("440x430")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    x = (root.winfo_screenwidth() // 2) - (440 // 2)
    y = (root.winfo_screenheight() // 2) - (430 // 2)
    root.geometry(f"+{x}+{y}")

    tk.Label(root, text="GESTOR DOCUMENTAL MUNICIPAL", font=("Helvetica", 13, "bold"), pady=10).pack()
    
    tk.Button(root, text="1. Unificación de Legajo", font=("Helvetica", 10, "bold"), bg="#2b5797", fg="white", width=38, command=lambda: (root.withdraw(), modulo_unificacion_legajo(root), root.destroy())).pack(pady=4)
    tk.Button(root, text="2. Múltiples Contraseñas", font=("Helvetica", 10, "bold"), bg="#007acc", fg="white", width=38, command=lambda: (root.withdraw(), modulo_gestion_contrasenas(root), root.destroy())).pack(pady=4)
    tk.Button(root, text="3. Ordenar Legajo (IA Local)", font=("Helvetica", 10, "bold"), bg="#8e44ad", fg="white", width=38, command=lambda: (root.withdraw(), modulo_ordenar_por_foliatura(root), root.destroy())).pack(pady=4)
    tk.Button(root, text="4. Base Datos: Folios Escaneados", font=("Helvetica", 10, "bold"), bg="#d35400", fg="white", width=38, command=lambda: (root.withdraw(), modulo_entrenamiento_base(root), root.destroy())).pack(pady=4)
    tk.Button(root, text="5. Indexar Legajo (Visual + OCR)", font=("Helvetica", 10, "bold"), bg="#27ae60", fg="white", width=38, command=lambda: (root.withdraw(), modulo_clasificacion_marcadores(root), root.destroy())).pack(pady=4)
    tk.Button(root, text="6. Base Datos: Tipos Documentales", font=("Helvetica", 10, "bold"), bg="#c0392b", fg="white", width=38, command=lambda: (root.withdraw(), modulo_entrenamiento_docs(root), root.destroy())).pack(pady=4)

    root.mainloop()


if __name__ == "__main__":
    menu_principal()