import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Importation de la fonction simuler du script existant
try:
    from lancer_simulation import simuler
except ImportError:
    print("Erreur : lancer_simulation.py doit être dans le même dossier.")


class SimulationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulateur Moteur MCC — Python & Simulink")
        self.root.geometry("950x650")
        self.root.minsize(800, 500)

        # Application d'un style propre
        style = ttk.Style()
        style.theme_use("clam")

        # --- Organisation en 2 Panneaux (Gauche: Contrôles / Droite: Graphiques) ---
        panneau_gauche = ttk.LabelFrame(root, text=" Configuration ", padding=15)
        panneau_gauche.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        panneau_droite = ttk.Frame(root, padding=10)
        panneau_droite.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Champs de saisie ---
        ttk.Label(panneau_gauche, text="Nom du modèle Simulink :").pack(anchor=tk.W, pady=(5, 2))
        self.ent_modele = ttk.Entry(panneau_gauche, width=25)
        self.ent_modele.insert(0, "modele_moteur")
        self.ent_modele.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(panneau_gauche, text="Consigne PWM (%) :").pack(anchor=tk.W, pady=(5, 2))
        self.var_pwm = tk.DoubleVar(value=15.0)
        self.spin_pwm = ttk.Spinbox(panneau_gauche, from_=0, to=100, increment=1, textvariable=self.var_pwm)
        self.spin_pwm.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(panneau_gauche, text="Durée (secondes) :").pack(anchor=tk.W, pady=(5, 2))
        self.var_duree = tk.DoubleVar(value=1.5)
        self.spin_duree = ttk.Spinbox(panneau_gauche, from_=0.1, to=60.0, increment=0.5, textvariable=self.var_duree)
        self.spin_duree.pack(fill=tk.X, pady=(0, 15))

        # --- Bouton de lancement ---
        self.btn_lancer = ttk.Button(panneau_gauche, text="▶ Lancer Simulation", command=self.executer_simulation)
        self.btn_lancer.pack(fill=tk.X, pady=10)

        # --- Zone d'affichage des résultats texte ---
        ttk.Label(panneau_gauche, text="Statut & Résumé :").pack(anchor=tk.W, pady=(15, 2))
        self.txt_resultats = tk.Text(panneau_gauche, width=30, height=12, state=tk.DISABLED, bg="#f8f9fa", font=("Consolas", 9))
        self.txt_resultats.pack(fill=tk.BOTH, expand=True)

        # --- Intégration du graphique Matplotlib ---
        self.fig, (self.ax_i, self.ax_w) = plt.subplots(2, 1, figsize=(6, 5), sharex=True)
        self.fig.tight_layout(pad=3.0)

        self.ax_i.set_ylabel("Courant (A)")
        self.ax_i.grid(True, linestyle="--", alpha=0.6)

        self.ax_w.set_xlabel("Temps (s)")
        self.ax_w.set_ylabel("Vitesse (rad/s)")
        self.ax_w.grid(True, linestyle="--", alpha=0.6)

        self.canvas = FigureCanvasTkAgg(self.fig, master=panneau_droite)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def executer_simulation(self):
        modele = self.ent_modele.get().strip()
        try:
            pwm = float(self.var_pwm.get())
            duree = float(self.var_duree.get())
        except ValueError:
            messagebox.showerror("Erreur", "Veuillez entrer des valeurs numériques valides.")
            return

        # Désactivation temporaire du bouton pendant le calcul MATLAB
        self.btn_lancer.config(state=tk.DISABLED, text="Simulation MATLAB en cours...")
        self.root.update()

        try:
            # Appel de la fonction simuler du pont Python-MATLAB
            chemin, donnees = simuler(modele, pwm, duree)

            i = donnees["courant"]
            w = donnees["vitesse"]
            t_i = donnees["temps_courant"]
            t_w = donnees["temps_vitesse"]

            # Tracé des nouvelles courbes
            self.ax_i.clear()
            self.ax_w.clear()

            self.ax_i.plot(t_i, i, color="#1f77b4", linewidth=1.5, label="Courant i(t)")
            self.ax_i.set_ylabel("Courant (A)")
            self.ax_i.grid(True, linestyle="--", alpha=0.6)
            self.ax_i.legend(loc="upper right")

            self.ax_w.plot(t_w, w, color="#ff7f0e", linewidth=1.5, label="Vitesse ω(t)")
            self.ax_w.set_xlabel("Temps (s)")
            self.ax_w.set_ylabel("Vitesse (rad/s)")
            self.ax_w.grid(True, linestyle="--", alpha=0.6)
            self.ax_w.legend(loc="upper right")

            self.canvas.draw()

            # Mise à jour du résumé textuel
            resume = (
                f"✔ Simulation terminée\n"
                f"----------------------\n"
                f"Points mesurés : {len(i)}\n\n"
                f"Courant (A) :\n"
                f"  Max   : {max(i):.4f} A\n"
                f"  Final : {i[-1]:.4f} A\n\n"
                f"Vitesse (rad/s) :\n"
                f"  Max   : {max(w):.2f} rad/s\n"
                f"  Final : {w[-1]:.2f} rad/s\n\n"
                f"Fichier créé :\n"
                f"{os.path.basename(chemin)}"
            )

            self.afficher_texte(resume)

        except Exception as e:
            messagebox.showerror("Erreur de simulation", f"Échec de l'exécution :\n{e}")
            self.afficher_texte(f"❌ Erreur :\n{e}")
        finally:
            self.btn_lancer.config(state=tk.NORMAL, text="▶ Lancer Simulation")

    def afficher_texte(self, texte):
        self.txt_resultats.config(state=tk.NORMAL)
        self.txt_resultats.delete("1.0", tk.END)
        self.txt_resultats.insert(tk.END, texte)
        self.txt_resultats.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()