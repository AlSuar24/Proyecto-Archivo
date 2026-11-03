import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from PIL import ImageStat
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

CLAVE_POR_DEFECTO = "archivo2025"
CARATULA_BASE_NOMBRE = "CARATULA BASE OFICIAL.pdf"


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


def procesar_unificacion():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    # 1. Solicitar el número de legajo
    entrada_usuario = simpledialog.askstring(
        "Número de Legajo",
        "Ingrese el número de legajo:",
        parent=root,
    )

    if not entrada_usuario or not entrada_usuario.strip():
        messagebox.showwarning(
            "Cancelado", "No se ingresó ningún número de legajo."
        )
        root.destroy()
        return

    # Limpia el número base y arma el formato con /00 para la carátula
    num_puro = entrada_usuario.strip().rstrip("/")
    if num_puro.endswith("/00"):
        num_puro = num_puro[:-3]

    legajo_caratula = f"{num_puro}/00"

    # 2. Localizar la Carátula Base Oficial
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
            root.destroy()
            return

    try:
        # Lectura de la carátula base
        lector_base = PdfReader(ruta_caratula)
        if lector_base.is_encrypted:
            lector_base.decrypt(CLAVE_POR_DEFECTO)

        pagina_base = lector_base.pages[0]
        ancho = float(pagina_base.mediabox.width)
        alto = float(pagina_base.mediabox.height)

        # Capa de texto con número de legajo tamaño 24 y posición fija
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(ancho, alto))
        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", 24)

        # Posición fija calibrada
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
        root.destroy()
        return

    # 3. Selección múltiple de documentos anexos
    es_primera_seleccion = True

    while True:
        if not es_primera_seleccion:
            agregar = messagebox.askyesno(
                "Agregar Documentos", "¿Desea agregar más archivos PDF?"
            )
            if not agregar:
                break

        # askopenfilenames permite seleccionar uno o varios archivos manteniendo Ctrl o Shift
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
                    root.destroy()
                    return
                break
            else:
                continue

        # Procesar en orden cada archivo seleccionado del lote
        for archivo in archivos_seleccionados:
            try:
                lector_anexo = PdfReader(archivo)

                # Desbloqueo automático si el anexo tiene contraseña
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

                # Filtrar páginas: se descartan las que estén visualmente en blanco
                total_paginas = len(lector_anexo.pages)
                for idx in range(total_paginas):
                    if not es_pagina_en_blanco_visual(archivo, idx):
                        writer_final.add_page(lector_anexo.pages[idx])

            except Exception as e:
                messagebox.showerror(
                    "Error al procesar archivo",
                    f"No se pudo procesar el archivo '{os.path.basename(archivo)}':\n{str(e)}",
                )

        es_primera_seleccion = False

    # 4. Guardar archivo final unificado como 'LEGAJO [número]'
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
        root.destroy()
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
    finally:
        root.destroy()


if __name__ == "__main__":
    procesar_unificacion()