import joblib, pandas as pd
m = joblib.load("modele/modele_regulateur.joblib")
r = pd.read_csv("test/dataset/resume_campagne.csv")
r = r[r.utilisable]
r["pwm_predit"] = m["statique_droite"].predict(r[["vitesse_ss_rad_s"]].values)
r["erreur"] = r.pwm_predit - r.pwm_nominal_pct
print(r[["pwm_nominal_pct", "vitesse_ss_rad_s", "pwm_predit", "erreur"]])