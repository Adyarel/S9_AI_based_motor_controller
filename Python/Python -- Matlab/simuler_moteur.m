function chemin = simuler_moteur(modele, pwm_pct, duree, dossier)
% SIMULER_MOTEUR  Simule le modèle Simulink et écrit un CSV au format clean_csv_...
%   chemin = simuler_moteur('modele_moteur', 15, 1.5, 'C:/mon/dossier')
%   Le modèle doit lire la variable pwm_pct et avoir 2 blocs Out :
%   Out1 = courant (A), Out2 = vitesse (rad/s).

    Te  = 0.0011985;      % période d'échantillonnage du courant (s)
    dec = 0.00059925;     % décalage de la mesure de vitesse (s)

    if ~isfolder(dossier), mkdir(dossier); end

    % 1) consigne -> workspace de base, lu par le modèle
    assignin('base', 'pwm_pct', pwm_pct);

    % 2) simulation
    load_system(modele);
    set_param(modele, 'SaveFormat', 'Array');
    out = sim(modele, 'StopTime', num2str(duree));
    if size(out.yout, 2) < 2
        error('Le modèle doit avoir 2 blocs Out (courant, vitesse).');
    end

    % 3) rééchantillonnage sur les grilles de temps du moteur réel
    ti = (0:Te:duree-Te)';
    tw = ti + dec;
    courant = interp1(out.tout, out.yout(:,1), ti, 'linear', 'extrap');
    vitesse = interp1(out.tout, out.yout(:,2), tw, 'linear', 'extrap');

    % 4) table + écriture du CSV
    n = numel(ti);
    pwm_valeur = repmat(round(pwm_pct*799/100), n, 1);
    pwm_col    = repmat(pwm_pct, n, 1);
    date_col   = repmat(string(datetime('now', 'Format', 'yyyy-MM-dd HH:mm:ss')), n, 1);

    T = table(ti, courant, tw, vitesse, pwm_valeur, pwm_col, date_col, ...
        'VariableNames', {'temps_courant_s','courant_A','temps_vitesse_s', ...
                          'vitesse_rad_s','pwm_valeur','pwm_pct','date'});

    nom = sprintf('PWM%d-%.1fs_%s.csv', round(pwm_pct), duree, ...
        char(datetime('now', 'Format', 'yyyyMMdd_HHmmss')));
    chemin = fullfile(dossier, nom);
    writetable(T, chemin);
    fprintf('%d points simulés écrits dans %s\n', n, chemin);
end
