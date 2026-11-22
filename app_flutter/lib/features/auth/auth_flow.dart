import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../data/services/api_service.dart';
import '../../state/app_state.dart';

/// Authentification multi-profils : connexion, création de compte, OTP 6 chiffres.
class AuthFlow extends StatefulWidget {
  const AuthFlow({super.key});

  @override
  State<AuthFlow> createState() => _AuthFlowState();
}

class _AuthFlowState extends State<AuthFlow> {
  bool _registerMode = false;
  bool _obscure = true;

  final _email = TextEditingController();
  final _password = TextEditingController();
  final _fullName = TextEditingController();
  final _birthYear = TextEditingController();
  String _role = 'patient';
  String _specialty = 'diabetologist';
  String _diabetesType = 'type_2';
  bool _consent = false;
  final _otp = TextEditingController();

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _fullName.dispose();
    _birthYear.dispose();
    _otp.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return Scaffold(
      body: DfScaffoldBackground(
        child: SafeArea(
          child: SingleChildScrollView(
            child: DfContentFrame(
              maxWidth: 520,
              padding: const EdgeInsets.fromLTRB(24, 40, 24, 40),
              child: auth.status == SessionStatus.pendingOtp
                  ? _buildOtp(context, auth)
                  : _buildCredentials(context, auth),
            ),
          ),
        ),
      ),
    );
  }

  // -----------------------------------------------------------------------
  Widget _buildCredentials(BuildContext context, AuthProvider auth) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 62,
          height: 62,
          decoration: const BoxDecoration(
            shape: BoxShape.circle,
            gradient: DfGradients.copperSheen,
          ),
          child: Center(
            child: Text('DF',
                style: DfType.h3.copyWith(color: DfColors.ink, fontSize: 20)),
          ),
        ),
        const SizedBox(height: 26),
        Text('PODOTRACE', style: DfType.overline),
        const SizedBox(height: 10),
        Text(
          _registerMode
              ? 'Créer votre\ncompte sécurisé'
              : 'Reprendre\nle suivi',
          style: DfType.display.copyWith(fontSize: 34),
        ),
        const SizedBox(height: 12),
        Text(
          _registerMode
              ? 'Un code à 6 chiffres vous sera envoyé par email pour vérifier votre adresse.'
              : 'Vos données de santé sont chiffrées et accessibles uniquement par vous.',
          style: DfType.caption.copyWith(height: 1.6),
        ),
        const SizedBox(height: 30),
        if (_registerMode) ...[
          _field(
            controller: _fullName,
            label: 'Nom complet',
            icon: Icons.person_outline_rounded,
            textCapitalization: TextCapitalization.words,
          ),
          const SizedBox(height: 14),
        ],
        _field(
          controller: _email,
          label: 'Adresse email',
          icon: Icons.alternate_email_rounded,
          keyboardType: TextInputType.emailAddress,
        ),
        const SizedBox(height: 14),
        _field(
          controller: _password,
          label: 'Mot de passe',
          icon: Icons.lock_outline_rounded,
          obscure: _obscure,
          suffix: IconButton(
            onPressed: () => setState(() => _obscure = !_obscure),
            icon: Icon(
              _obscure
                  ? Icons.visibility_outlined
                  : Icons.visibility_off_outlined,
              size: 18,
              color: DfColors.muted,
            ),
          ),
        ),
        if (_registerMode) ...[
          const SizedBox(height: 20),
          Text('JE SUIS…', style: DfType.overline.copyWith(fontSize: 9)),
          const SizedBox(height: 10),
          Row(
            children: [
              _roleChip('patient', 'Patient', Icons.favorite_border_rounded),
              const SizedBox(width: 10),
              _roleChip(
                  'practitioner', 'Praticien', Icons.medical_services_outlined),
            ],
          ),
          if (_role == 'practitioner') ...[
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _specialty,
              dropdownColor: DfColors.plumLift,
              decoration: const InputDecoration(labelText: 'Spécialité'),
              items: const [
                DropdownMenuItem(
                    value: 'diabetologist', child: Text('Diabétologue')),
                DropdownMenuItem(value: 'podiatrist', child: Text('Podologue')),
                DropdownMenuItem(value: 'nurse', child: Text('Infirmier·ère')),
                DropdownMenuItem(
                    value: 'physician', child: Text('Médecin généraliste')),
                DropdownMenuItem(value: 'other', child: Text('Autre')),
              ],
              onChanged: (v) =>
                  setState(() => _specialty = v ?? 'diabetologist'),
            ),
          ] else ...[
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: _diabetesType,
              dropdownColor: DfColors.plumLift,
              decoration: const InputDecoration(labelText: 'Type de diabète'),
              items: const [
                DropdownMenuItem(value: 'type_2', child: Text('Type 2')),
                DropdownMenuItem(value: 'type_1', child: Text('Type 1')),
                DropdownMenuItem(
                    value: 'gestational', child: Text('Gestationnel')),
                DropdownMenuItem(value: 'other', child: Text('Autre')),
                DropdownMenuItem(value: 'none', child: Text('Non diabétique')),
              ],
              onChanged: (v) => setState(() => _diabetesType = v ?? 'type_2'),
            ),
            const SizedBox(height: 14),
            _field(
              controller: _birthYear,
              label: 'Année de naissance',
              icon: Icons.cake_outlined,
              keyboardType: TextInputType.number,
            ),
          ],
          const SizedBox(height: 18),
          InkWell(
            onTap: () => setState(() => _consent = !_consent),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 22,
                  height: 22,
                  child: Checkbox(
                    value: _consent,
                    onChanged: (v) => setState(() => _consent = v ?? false),
                    activeColor: DfColors.copper,
                    checkColor: DfColors.ink,
                    side: const BorderSide(color: DfColors.copper),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'J\'accepte le traitement chiffré de mes données de santé et je '
                    'comprends qu\'il s\'agit d\'une aide à la décision, non d\'un diagnostic.',
                    style: DfType.caption.copyWith(height: 1.55),
                  ),
                ),
              ],
            ),
          ),
        ],
        if (auth.error != null) ...[
          const SizedBox(height: 16),
          _errorBox(auth.error!),
        ],
        const SizedBox(height: 26),
        DfPrimaryButton(
          label: _registerMode ? 'Créer mon compte' : 'Se connecter',
          icon: _registerMode
              ? Icons.person_add_alt_rounded
              : Icons.login_rounded,
          expand: true,
          loading: auth.busy,
          onPressed: auth.busy ? null : () => _submit(auth),
        ),
        const SizedBox(height: 16),
        Center(
          child: TextButton(
            onPressed: () => setState(() {
              _registerMode = !_registerMode;
            }),
            child: Text(
              _registerMode
                  ? 'J\'ai déjà un compte — se connecter'
                  : 'Créer un compte patient ou praticien',
              style: DfType.caption.copyWith(color: DfColors.copperLight),
            ),
          ),
        ),
        const SizedBox(height: 8),
        const DfdDisclaimer(),
      ],
    );
  }

  Widget _buildOtp(BuildContext context, AuthProvider auth) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        IconButton(
          onPressed: () => context.read<AuthProvider>().logout(),
          icon: const Icon(Icons.arrow_back_rounded, color: DfColors.creamDim),
          alignment: Alignment.centerLeft,
        ),
        const SizedBox(height: 18),
        Text('VÉRIFICATION', style: DfType.overline),
        const SizedBox(height: 10),
        Text('Code à 6 chiffres', style: DfType.display.copyWith(fontSize: 34)),
        const SizedBox(height: 12),
        Text(
          'Code envoyé à ${auth.pendingEmail ?? ''}. Il expire dans 15 minutes.',
          style: DfType.caption.copyWith(height: 1.6),
        ),
        if (auth.devOtp != null) ...[
          const SizedBox(height: 16),
          DfGlassCard(
            accent: DfColors.info,
            padding: const EdgeInsets.all(14),
            child: Text(
              'Environnement de développement — code : ${auth.devOtp}',
              style: DfType.caption.copyWith(color: DfColors.info),
            ),
          ),
        ],
        const SizedBox(height: 28),
        TextField(
          controller: _otp,
          keyboardType: TextInputType.number,
          textAlign: TextAlign.center,
          maxLength: 6,
          style: DfType.metric.copyWith(fontSize: 30, letterSpacing: 14),
          decoration: const InputDecoration(
            counterText: '',
            hintText: '••••••',
          ),
        ),
        if (auth.error != null) ...[
          const SizedBox(height: 14),
          _errorBox(auth.error!),
        ],
        const SizedBox(height: 24),
        DfPrimaryButton(
          label: 'Valider le code',
          icon: Icons.verified_outlined,
          expand: true,
          loading: auth.busy,
          onPressed: auth.busy ? null : () => auth.verifyOtp(_otp.text.trim()),
        ),
        const SizedBox(height: 14),
        Center(
          child: TextButton(
            onPressed: () async {
              final api = context.read<ApiService>();
              final code = await api.resendOtp(auth.pendingEmail ?? '');
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      code == null
                          ? 'Nouveau code envoyé par email.'
                          : 'Code de développement : $code',
                    ),
                  ),
                );
              }
            },
            child: Text('Recevoir un nouveau code',
                style: DfType.caption.copyWith(color: DfColors.copperLight)),
          ),
        ),
      ],
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    bool obscure = false,
    Widget? suffix,
    TextInputType? keyboardType,
    TextCapitalization textCapitalization = TextCapitalization.none,
  }) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      keyboardType: keyboardType,
      textCapitalization: textCapitalization,
      style: DfType.body.copyWith(color: DfColors.cream),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 18, color: DfColors.muted),
        suffixIcon: suffix,
      ),
    );
  }

  Widget _roleChip(String value, String label, IconData icon) {
    final selected = _role == value;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _role = value),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(
            gradient: selected ? DfGradients.copperSheen : null,
            color: selected ? null : DfColors.plumSoft,
            borderRadius: BorderRadius.circular(13),
            border: Border.all(
              color: selected ? Colors.transparent : DfColors.hairline,
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon,
                  size: 16, color: selected ? DfColors.ink : DfColors.creamDim),
              const SizedBox(width: 8),
              Text(
                label,
                style: DfType.caption.copyWith(
                  color: selected ? DfColors.ink : DfColors.creamDim,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _errorBox(String message) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: DfColors.critical.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: DfColors.critical.withValues(alpha: 0.4)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline_rounded,
              size: 16, color: DfColors.critical),
          const SizedBox(width: 10),
          Expanded(
            child: Text(message,
                style: DfType.caption
                    .copyWith(color: DfColors.creamDim, height: 1.5)),
          ),
        ],
      ),
    );
  }

  Future<void> _submit(AuthProvider auth) async {
    FocusScope.of(context).unfocus();
    if (_registerMode) {
      await auth.register(
        email: _email.text.trim(),
        password: _password.text,
        fullName: _fullName.text.trim(),
        consent: _consent,
        role: _role,
        specialty: _role == 'practitioner' ? _specialty : null,
        diabetesType: _diabetesType,
        birthYear: int.tryParse(_birthYear.text.trim()),
      );
    } else {
      await auth.login(_email.text.trim(), _password.text);
    }
  }
}
