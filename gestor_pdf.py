import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

CLAVE_POR_DEFECTO = "archivo2025"
CARATULA_BASE_NOMBRE = "CARATULA BASE OFICIAL.pdf"


def es_pagina_en_blanco(pagina) -> bool:
    """Determina si una página no contiene texto ni imágenes."""
    # 1. Comprueba si existe contenido de texto
    texto = pagina.extract_text() or ""
    if texto.strip():
        return False

    # 2. Comprueba si contiene imágenes u objetos visuales en sus recursos
    try:
        recursos = pagina.get("/Resources", {})
        if "/XObject" in recursos:
            xobjects = recursos["/XObject"]
            for obj_key in xobjects:
                obj = xobjects[obj_key]
                if obj.get("/Subtype") == "/Image":
                    return False
    except Exception:
        # En caso de no poder parsear recursos específicos, se asume que contiene contenido por seguridad
        return False

    return True


def procesar_unificacion():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    # 1. Solicitar el número de legajo
    entrada_usuario = simpledialog.askstring(
        "Número de Legajo",
        "Ingrese el número de legajo:",
        parent=root
    )

    if not entrada_usuario or not entrada_usuario.strip():
        messagebox.showwarning("Cancelado", "No se ingresó ningún número de legajo.")
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
        messagebox.showinfo("Carátula Oficial", f"Seleccione el archivo oficial ({CARATULA_BASE_NOMBRE})")
        ruta_caratula = filedialog.askopenfilename(
            title=f"Seleccionar {CARATULA_BASE_NOMBRE}",
            filetypes=[("Archivos PDF", "*.pdf")]
        )
        if not ruta_caratula:
            messagebox.showwarning("Cancelado", "Se requiere la carátula para continuar.")
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

        # Generar capa de texto con tamaño 24 y posición calibrada
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(ancho, alto))
        c.setFillColor(HexColor("#000000"))
        c.setFont("Helvetica-Bold", 24)

        # Posición fija
        c.drawString(ancho * 0.315, alto * 0.468, legajo_caratula)

        c.save()
        buffer.seek(0)

        lector_overlay = PdfReader(buffer)
        pagina_base.merge_page(lector_overlay.pages[0])

        writer_final = PdfWriter()
        writer_final.add_page(pagina_base)

    except Exception as e:
        messagebox.showerror("Error", f"No se pudo generar la carátula: {str(e)}")
        root.destroy()
        return

    # 3. Preguntar y agregar documentos anexos (filtrando páginas en blanco)
    while True:
        agregar = messagebox.askyesno("Agregar Documentos", "¿Desea agregar otro documento?")
        if not agregar:
            break

        archivo = filedialog.askopenfilename(
            title="Seleccionar documento a anexar",
            filetypes=[("Archivos PDF", "*.pdf")]
        )

        if not archivo:
            continue

        try:
            lector_anexo = PdfReader(archivo)

            # Desbloqueo automático si el anexo tiene contraseña
            if lector_anexo.is_encrypted:
                resultado = lector_anexo.decrypt(CLAVE_POR_DEFECTO)
                if resultado == 0:
                    clave_manual = simpledialog.askstring(
                        "Contraseña",
                        f"La clave por defecto falló para '{os.path.basename(archivo)}'. Ingrese la clave:",
                        parent=root
                    )
                    if clave_manual:
                        lector_anexo.decrypt(clave_manual)

            # Agregar solo las páginas que contengan información
            for pagina in lector_anexo.pages:
                if not es_pagina_en_blanco(pagina):
                    writer_final.add_page(pagina)

        except Exception as e:
            messagebox.showerror("Error al procesar archivo", f"No se pudo agregar el archivo:\n{str(e)}")

    # 4. Guardar archivo final unificado como 'LEGAJO [número]'
    nombre_archivo_sugerido = f"LEGAJO {num_puro}.pdf"

    ruta_guardado = filedialog.asksaveasfilename(
        title="Guardar legajo unificado como...",
        initialfile=nombre_archivo_sugerido,
        defaultextension=".pdf",
        filetypes=[("Archivos PDF", "*.pdf")],
        parent=root
    )

    if not ruta_guardado:
        messagebox.showwarning("Cancelado", "No se guardó el documento unificado.")
        root.destroy()
        return

    try:
        with open(ruta_guardado, "wb") as f_out:
            writer_final.write(f_out)
        writer_final.close()
        messagebox.showinfo("Éxito", f"Legajo guardado correctamente en:\n{ruta_guardado}")
    except Exception as e:
        messagebox.showerror("Error al guardar", f"No se pudo guardar el archivo final: {str(e)}")
    finally:
        root.destroy()


if __name__ == "__main__":
    procesar_unificacion()