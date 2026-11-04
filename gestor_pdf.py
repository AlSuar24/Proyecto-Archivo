import io
import os
import shutil
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import ImageStat
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

CLAVE_POR_DEFECTO = "archivo2025"
CARATULA_BASE_NOMBRE = "CARATULA BASE OFICIAL.pdf"


# ==============================================================================
# UTILIDADES GENERALES
# ==============================================================================

def es_pagina_en_blanco_visual(
    pdf_path: str, num_pag: int, umbral_brillo: float = 250.0
) -> bool:
    """Renderiza la página en memoria y evalúa si está en blanco o vacía."""
    try:
        doc = pdfium.PdfDocument(pdf_path, password=CLAVE_POR_DEFECTO)
        page = doc.get_page(num_pag)
        bitmap = page.render(scale=0.5)
        pil_image = bitmap.to_pil().convert("L")

        stat = ImageStat.Stat(pil_image)
        brillo_promedio = stat.mean[0]
        desviacion = stat.stddev[0]

        if brillo_promedio >= umbral_brillo and desviacion < 8.0:
            return True
        return False
    except Exception:
        return False


# ==============================================================================
# MÓDULO 1: UNIFICACIÓN DE LEGAJO
# ==============================================================================

def modulo_unificacion_legajo(root):
    entrada_usuario = simpledialog.askstring(
        "Número de Legajo",
        "Ingrese el número de legajo:",
        parent=root,
    )

    if not entrada_usuario or not entrada_usuario.strip():
        messagebox.showwarning(
            "Cancelado", "No se ingresó ningún número de legajo."
        )
        return

    num_puro = entrada_usuario.strip().rstrip("/")
    if num_puro.endswith("/00"):
        num_puro = num_puro[:-3]

    legajo_caratula = f"{num_puro}/00"

    ruta_caratula = os.path.join(os.getcwd(), CARATULA_BASE_NOMBRE)
    if not os.path.exists(ruta_caratula):
        messagebox.showinfo(
            "Carátula Oficial",
            f"Seleccione el archivo oficial ({CARATULA_BASE_NOMBRE})",
        )
        ruta_caratula = filedialog.askopenfilename(
            title=f"Seleccionar {CARATULA_BASE_NOMBRE}",
            filetypes=[("Archivos PDF", "*.pdf")],
        )
        if not ruta_caratula:
            messagebox.showwarning(
                "Cancelado", "Se requiere la carátula para continuar."
            )
            return

    try:
        lector_base = PdfReader(ruta_caratula)
        if lector_base.is_encrypted:
            lector_base.decrypt(CLAVE_POR_DEFECTO)

        pagina_base = lector_base.pages[0]
        ancho = float(pagina_base.mediabox.width)
        alto = float(pagina_base.mediabox.height)

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(ancho, alto))
        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", 24)
        c.drawString(ancho * 0.315, alto * 0.468, legajo_caratula)
        c.save()
        buffer.seek(0)

        lector_overlay = PdfReader(buffer)
        pagina_base.merge_page(lector_overlay.pages[0])

        writer_final = PdfWriter()
        writer_final.add_page(pagina_base)

    except Exception as e:
        messagebox.showerror(
            "Error", f"No se pudo generar la carátula: {str(e)}"
        )
        return

    es_primera_seleccion = True

    while True:
        if not es_primera_seleccion:
            agregar = messagebox.askyesno(
                "Agregar Documentos", "¿Desea agregar más archivos PDF?"
            )
            if not agregar:
                break

        archivos_seleccionados = filedialog.askopenfilenames(
            title="Seleccionar archivos PDF a anexar (puede seleccionar varios)"
            if not es_primera_seleccion
            else "Seleccionar primeros archivos PDF a anexar (puede seleccionar varios)",
            filetypes=[("Archivos PDF", "*.pdf")],
        )

        if not archivos_seleccionados:
            if es_primera_seleccion:
                confirmar = messagebox.askyesno(
                    "Sin documentos",
                    "No seleccionó ningún archivo. ¿Desea continuar y guardar solo la carátula?",
                )
                if not confirmar:
                    return
                break
            else:
                continue

        for archivo in archivos_seleccionados:
            try:
                lector_anexo = PdfReader(archivo)

                if lector_anexo.is_encrypted:
                    resultado = lector_anexo.decrypt(CLAVE_POR_DEFECTO)
                    if resultado == 0:
                        clave_manual = simpledialog.askstring(
                            "Contraseña",
                            f"La clave por defecto falló para '{os.path.basename(archivo)}'. Ingrese la clave:",
                            parent=root,
                        )
                        if clave_manual:
                            lector_anexo.decrypt(clave_manual)

                total_paginas = len(lector_anexo.pages)
                for idx in range(total_paginas):
                    if not es_pagina_en_blanco_visual(archivo, idx):
                        writer_final.add_page(lector_anexo.pages[idx])

            except Exception as e:
                messagebox.showerror(
                    "Error al procesar archivo",
                    f"No se pudo procesar '{os.path.basename(archivo)}':\n{str(e)}",
                )

        es_primera_seleccion = False

    nombre_archivo_sugerido = f"LEGAJO {num_puro}.pdf"

    ruta_guardado = filedialog.asksaveasfilename(
        title="Guardar legajo unificado como...",
        initialfile=nombre_archivo_sugerido,
        defaultextension=".pdf",
        filetypes=[("Archivos PDF", "*.pdf")],
        parent=root,
    )

    if not ruta_guardado:
        messagebox.showwarning(
            "Cancelado", "No se guardó el documento unificado."
        )
        return

    try:
        with open(ruta_guardado, "wb") as f_out:
            writer_final.write(f_out)
        writer_final.close()
        messagebox.showinfo(
            "Éxito", f"Legajo guardado correctamente en:\n{ruta_guardado}"
        )
    except Exception as e:
        messagebox.showerror(
            "Error al guardar", f"No se pudo guardar el archivo final: {str(e)}"
        )


# ==============================================================================
# MÓDULO 2: GESTIÓN MASIVA DE CONTRASEÑAS (REEMPLAZO EN ORIGEN)
# ==============================================================================

def modulo_gestion_contrasenas(root):
    # Ventana modal con botones específicos "Quitar" y "Agregar"
    eleccion = {"accion": None}

    ventana_opcion = tk.Toplevel(root)
    ventana_opcion.title("Múltiples Contraseñas")
    ventana_opcion.geometry("360x170")
    ventana_opcion.resizable(False, False)
    ventana_opcion.attributes("-topmost", True)

    ancho_p = ventana_opcion.winfo_screenwidth()
    alto_p = ventana_opcion.winfo_screenheight()
    x = (ancho_p // 2) - (360 // 2)
    y = (alto_p // 2) - (170 // 2)
    ventana_opcion.geometry(f"+{x}+{y}")

    def set_accion(valor):
        eleccion["accion"] = valor
        ventana_opcion.destroy()

    tk.Label(
        ventana_opcion,
        text="MÚLTIPLES CONTRASEÑAS",
        font=("Helvetica", 11, "bold"),
        pady=8,
    ).pack()

    tk.Label(
        ventana_opcion,
        text="Seleccione la acción a realizar sobre los archivos:",
        font=("Helvetica", 9),
        fg="#555555",
    ).pack(pady=2)

    frame_btns = tk.Frame(ventana_opcion)
    frame_btns.pack(pady=12)

    btn_quitar = tk.Button(
        frame_btns,
        text="Quitar Contraseña",
        font=("Helvetica", 9, "bold"),
        bg="#c0392b",
        fg="white",
        padx=10,
        pady=5,
        command=lambda: set_accion("quitar"),
        cursor="hand2",
    )
    btn_quitar.pack(side="left", padx=8)

    btn_agregar = tk.Button(
        frame_btns,
        text="Agregar Contraseña",
        font=("Helvetica", 9, "bold"),
        bg="#27ae60",
        fg="white",
        padx=10,
        pady=5,
        command=lambda: set_accion("agregar"),
        cursor="hand2",
    )
    btn_agregar.pack(side="left", padx=8)

    ventana_opcion.wait_window()

    accion = eleccion["accion"]
    if not accion:
        return

    # 1. Selección de carpeta
    carpeta = filedialog.askdirectory(
        title="Seleccionar carpeta donde están los PDFs"
    )

    if not carpeta:
        messagebox.showwarning("Cancelado", "No se seleccionó ninguna carpeta.")
        return

    archivos_pdf = [
        os.path.join(carpeta, f)
        for f in os.listdir(carpeta)
        if f.lower().endswith(".pdf")
    ]

    if not archivos_pdf:
        messagebox.showinfo(
            "Sin archivos", "No se encontraron archivos PDF en la carpeta seleccionada."
        )
        return

    # MODO QUITAR CONTRASEÑA
    if accion == "quitar":
        clave_actual = simpledialog.askstring(
            "Quitar Contraseña",
            f"Ingrese la contraseña actual de los PDFs (vacío para usar '{CLAVE_POR_DEFECTO}'):",
            parent=root,
        )

        if clave_actual is None:
            return

        clave_usar = clave_actual.strip() if clave_actual.strip() else CLAVE_POR_DEFECTO

        exitosos = 0
        fallidos = []

        for archivo in archivos_pdf:
            nombre = os.path.basename(archivo)
            try:
                lector = PdfReader(archivo)
                if lector.is_encrypted:
                    res = lector.decrypt(clave_usar)
                    if res == 0:
                        fallidos.append(f"{nombre} (Contraseña incorrecta)")
                        continue

                writer = PdfWriter()
                for pag in lector.pages:
                    writer.add_page(pag)

                # Escritura en temporal y reemplazo directo del archivo original
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    temp_path = tmp.name
                    writer.write(tmp)
                writer.close()

                shutil.move(temp_path, archivo)
                exitosos += 1

            except Exception as e:
                fallidos.append(f"{nombre} ({str(e)})")

        res_msg = f"Archivos desbloqueados y reemplazados con éxito: {exitosos}"
        if fallidos:
            res_msg += "\n\nArchivos omitidos:\n" + "\n".join(fallidos[:10])
        messagebox.showinfo("Proceso finalizado", res_msg)

    # MODO AGREGAR CONTRASEÑA
    elif accion == "agregar":
        nueva_clave = simpledialog.askstring(
            "Agregar Contraseña",
            "Ingrese la nueva contraseña que desea colocar a todos los PDFs:",
            show="*",
            parent=root,
        )

        if not nueva_clave:
            messagebox.showwarning(
                "Cancelado", "No se ingresó ninguna contraseña."
            )
            return

        exitosos = 0
        fallidos = []

        for archivo in archivos_pdf:
            nombre = os.path.basename(archivo)
            try:
                lector = PdfReader(archivo)

                if lector.is_encrypted:
                    res = lector.decrypt(CLAVE_POR_DEFECTO)
                    if res == 0:
                        fallidos.append(f"{nombre} (Ya posee otra contraseña previa)")
                        continue

                writer = PdfWriter()
                for pag in lector.pages:
                    writer.add_page(pag)

                writer.encrypt(nueva_clave)

                # Escritura en temporal y reemplazo directo del archivo original
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    temp_path = tmp.name
                    writer.write(tmp)
                writer.close()

                shutil.move(temp_path, archivo)
                exitosos += 1

            except Exception as e:
                fallidos.append(f"{nombre} ({str(e)})")

        res_msg = f"Archivos protegidos y reemplazados con éxito: {exitosos}"
        if fallidos:
            res_msg += "\n\nArchivos omitidos:\n" + "\n".join(fallidos[:10])
        messagebox.showinfo("Proceso finalizado", res_msg)


# ==============================================================================
# MENÚ PRINCIPAL
# ==============================================================================

def menu_principal():
    root = tk.Tk()
    root.title("Gestor Integral de PDFs")
    root.geometry("420x230")
    root.resizable(False, False)
    root.attributes("-topmost", True)

    ancho_pantalla = root.winfo_screenwidth()
    alto_pantalla = root.winfo_screenheight()
    x = (ancho_pantalla // 2) - (420 // 2)
    y = (alto_pantalla // 2) - (230 // 2)
    root.geometry(f"+{x}+{y}")

    lbl_titulo = tk.Label(
        root,
        text="GESTOR DE DOCUMENTOS PDF",
        font=("Helvetica", 13, "bold"),
        pady=10,
    )
    lbl_titulo.pack()

    lbl_sub = tk.Label(
        root,
        text="Seleccione la operación que desea ejecutar:",
        font=("Helvetica", 10),
        fg="#555555",
    )
    lbl_sub.pack(pady=2)

    def ejecutar_unificacion():
        root.withdraw()
        modulo_unificacion_legajo(root)
        root.destroy()

    def ejecutar_contrasenas():
        root.withdraw()
        modulo_gestion_contrasenas(root)
        root.destroy()

    btn_unificar = tk.Button(
        root,
        text="1. Unificación de Legajo (Carátula y Filtro)",
        font=("Helvetica", 10, "bold"),
        bg="#2b5797",
        fg="white",
        padx=10,
        pady=6,
        command=ejecutar_unificacion,
        cursor="hand2",
    )
    btn_unificar.pack(fill="x", padx=35, pady=8)

    btn_pass = tk.Button(
        root,
        text="2. Múltiples Contraseñas",
        font=("Helvetica", 10, "bold"),
        bg="#007acc",
        fg="white",
        padx=10,
        pady=6,
        command=ejecutar_contrasenas,
        cursor="hand2",
    )
    btn_pass.pack(fill="x", padx=35, pady=4)

    root.mainloop()


if __name__ == "__main__":
    menu_principal()