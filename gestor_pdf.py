import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pypdf import PdfReader, PdfWriter


# ==========================================================
# MÓDULO 1: UNIFICACIÓN DE LEGAJO (CON VENTANAS)
# ==========================================================
class UnificacionLegajo:
    """Módulo para unir múltiples archivos PDF mediante explorador de archivos."""

    @staticmethod
    def ejecutar() -> None:
        # 1. Ventana para seleccionar la carpeta con los PDFs
        carpeta_origen = filedialog.askdirectory(
            title="Seleccionar carpeta con los PDFs a unificar"
        )
        if not carpeta_origen:
            return  # El usuario canceló

        # 2. Obtener y ordenar los PDFs
        archivos = sorted([
            f for f in os.listdir(carpeta_origen) 
            if f.lower().endswith(".pdf")
        ])

        if not archivos:
            messagebox.showwarning(
                "Sin archivos", 
                "No se encontraron archivos PDF en la carpeta seleccionada."
            )
            return

        # 3. Ventana para guardar el PDF final
        archivo_salida = filedialog.asksaveasfilename(
            title="Guardar legajo unificado como...",
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialfile="Legajo_Unificado.pdf"
        )
        if not archivo_salida:
            return

        escritor = PdfWriter()
        archivos_agregados = 0
        omitidos_por_clave = []

        for nombre_archivo in archivos:
            ruta_completa = os.path.join(carpeta_origen, nombre_archivo)
            try:
                lector = PdfReader(ruta_completa)
                if lector.is_encrypted:
                    omitidos_por_clave.append(nombre_archivo)
                    continue

                for pagina in lector.pages:
                    escritor.add_page(pagina)

                archivos_agregados += 1
            except Exception as e:
                print(f"Error al leer {nombre_archivo}: {e}")

        if archivos_agregados > 0:
            with open(archivo_salida, "wb") as f_out:
                escritor.write(f_out)

            mensaje = f"Legajo creado exitosamente con {archivos_agregados} archivo(s).\n\nGuardado en:\n{archivo_salida}"
            if omitidos_por_clave:
                mensaje += f"\n\nArchivos omitidos por tener contraseña ({len(omitidos_por_clave)}):\n" + "\n".join(omitidos_por_clave)
            messagebox.showinfo("Éxito", mensaje)
        else:
            messagebox.showerror(
                "Error", 
                "No se pudo agregar ningún PDF. Verifica que no estén corruptos o protegidos."
            )


# ==========================================================
# MÓDULO 2: GESTIÓN DE SEGURIDAD (QUITAR / AGREGAR CONTRASEÑA)
# ==========================================================
class GestorSeguridadPDF:
    """Módulo para remover o aplicar protección con contraseñas masivas mediante ventanas."""

    @staticmethod
    def quitar_contrasena_masivo() -> None:
        # Carpeta origen
        carpeta_origen = filedialog.askdirectory(
            title="Seleccionar carpeta con los PDFs protegidos"
        )
        if not carpeta_origen:
            return

        archivos = [f for f in os.listdir(carpeta_origen) if f.lower().endswith(".pdf")]
        if not archivos:
            messagebox.showwarning("Aviso", "No hay archivos PDF en la carpeta seleccionada.")
            return

        # Carpeta destino
        carpeta_destino = filedialog.askdirectory(
            title="Seleccionar carpeta donde guardar los PDFs desbloqueados"
        )
        if not carpeta_destino:
            return

        # Ventana para pedir la contraseña
        password = simpledialog.askstring(
            "Contraseña requerida",
            "Ingrese la contraseña para desbloquear los PDFs:",
            show="*"
        )
        if not password:
            messagebox.showwarning("Cancelado", "No se ingresó contraseña. Operación cancelada.")
            return

        desbloqueados = 0
        fallidos = 0

        for archivo in archivos:
            ruta_in = os.path.join(carpeta_origen, archivo)
            ruta_out = os.path.join(carpeta_destino, archivo)

            try:
                lector = PdfReader(ruta_in)
                if lector.is_encrypted:
                    estado = lector.decrypt(password)
                    if estado == 0:
                        fallidos += 1
                        continue

                escritor = PdfWriter()
                for pagina in lector.pages:
                    escritor.add_page(pagina)

                with open(ruta_out, "wb") as f_out:
                    escritor.write(f_out)

                desbloqueados += 1
            except Exception:
                fallidos += 1

        messagebox.showinfo(
            "Proceso Finalizado",
            f"Archivos desbloqueados con éxito: {desbloqueados}\n"
            f"Archivos fallidos o con contraseña incorrecta: {fallidos}"
        )

    @staticmethod
    def agregar_contrasena_masivo() -> None:
        # Carpeta origen
        carpeta_origen = filedialog.askdirectory(
            title="Seleccionar carpeta con los PDFs a proteger"
        )
        if not carpeta_origen:
            return

        archivos = [f for f in os.listdir(carpeta_origen) if f.lower().endswith(".pdf")]
        if not archivos:
            messagebox.showwarning("Aviso", "No hay archivos PDF en la carpeta seleccionada.")
            return

        # Carpeta destino
        carpeta_destino = filedialog.askdirectory(
            title="Seleccionar carpeta donde guardar los PDFs protegidos"
        )
        if not carpeta_destino:
            return

        # Pedir y confirmar contraseña mediante cuadros de diálogo
        nueva_clave = simpledialog.askstring(
            "Nueva Contraseña",
            "Ingrese la contraseña a colocar en los PDFs:",
            show="*"
        )
        if not nueva_clave:
            messagebox.showwarning("Cancelado", "Operación cancelada.")
            return

        confirmacion = simpledialog.askstring(
            "Confirmar Contraseña",
            "Reingrese la contraseña para confirmar:",
            show="*"
        )
        if nueva_clave != confirmacion:
            messagebox.showerror("Error", "Las contraseñas no coinciden. Inténtalo nuevamente.")
            return

        protegidos = 0
        omitidos = 0

        for archivo in archivos:
            ruta_in = os.path.join(carpeta_origen, archivo)
            ruta_out = os.path.join(carpeta_destino, archivo)

            try:
                lector = PdfReader(ruta_in)
                if lector.is_encrypted:
                    omitidos += 1
                    continue

                escritor = PdfWriter()
                for pagina in lector.pages:
                    escritor.add_page(pagina)

                escritor.encrypt(user_password=nueva_clave)

                with open(ruta_out, "wb") as f_out:
                    escritor.write(f_out)

                protegidos += 1
            except Exception:
                omitidos += 1

        messagebox.showinfo(
            "Proceso Finalizado",
            f"Archivos protegidos correctamente: {protegidos}\n"
            f"Archivos omitidos o con error: {omitidos}"
        )


# ==========================================================
# INTERFAZ GRÁFICA PRINCIPAL (VENTANA DE BOTONES)
# ==========================================================
def iniciar_interfaz():
    ventana = tk.Tk()
    ventana.title("Gestor Integral de PDFs")
    ventana.geometry("420x330")
    ventana.resizable(False, False)

    # Configuración de estilos simples
    lbl_titulo = tk.Label(
        ventana, 
        text="Herramientas de Legajos y Seguridad", 
        font=("Segoe UI", 13, "bold"),
        pady=15
    )
    lbl_titulo.pack()

    btn_unificar = tk.Button(
        ventana,
        text="1. Unificación de Legajo",
        font=("Segoe UI", 10, "bold"),
        bg="#0288D1",
        fg="white",
        height=2,
        width=32,
        command=UnificacionLegajo.ejecutar
    )
    btn_unificar.pack(pady=6)

    btn_quitar_pass = tk.Button(
        ventana,
        text="2. Quitar Contraseña Masivamente",
        font=("Segoe UI", 10),
        bg="#546E7A",
        fg="white",
        height=2,
        width=32,
        command=GestorSeguridadPDF.quitar_contrasena_masivo
    )
    btn_quitar_pass.pack(pady=6)

    btn_poner_pass = tk.Button(
        ventana,
        text="3. Agregar Contraseña Masivamente",
        font=("Segoe UI", 10),
        bg="#37474F",
        fg="white",
        height=2,
        width=32,
        command=GestorSeguridadPDF.agregar_contrasena_masivo
    )
    btn_poner_pass.pack(pady=6)

    btn_salir = tk.Button(
        ventana,
        text="Cerrar",
        command=ventana.destroy,
        width=12
    )
    btn_salir.pack(pady=12)

    ventana.mainloop()


if __name__ == "__main__":
    iniciar_interfaz()