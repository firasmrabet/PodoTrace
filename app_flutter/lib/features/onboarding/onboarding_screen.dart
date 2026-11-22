import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/theme/df_theme.dart';
import '../../core/theme/df_widgets.dart';
import '../../state/app_state.dart';

class _OnboardingSlide {
  const _OnboardingSlide({
    required this.icon,
    required this.overline,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String overline;
  final String title;
  final String body;
}

const _slides = <_OnboardingSlide>[
  _OnboardingSlide(
    icon: Icons.monitor_heart_outlined,
    overline: 'Surveillance clinique',
    title: 'Votre plaie suivie\navec précision',
    body:
        'Chaque photographie est analysée pour mesurer la surface au centimètre '
        'carré près, cartographier les tissus et suivre la trajectoire de '
        'cicatrisation semaine après semaine.',
  ),
  _OnboardingSlide(
    icon: Icons.center_focus_strong_outlined,
    overline: 'Capture calibrée',
    title: 'Une photo,\nune mesure exacte',
    body:
        'Placez la gommette verte de 2 cm à côté de la plaie. Le cadrage vous '
        'guide en temps réel : niveau à bulle, netteté et luminosité sont '
        'contrôlés avant la prise de vue.',
  ),
  _OnboardingSlide(
    icon: Icons.health_and_safety_outlined,
    overline: 'Alertes & transmission',
    title: 'Détecter tôt,\nagir vite',
    body:
        'Les scores de risque infectieux et ischémique sont expliqués par une '
        'carte d\'attention clinique, et un rapport PDF complet peut être '
        'transmis à votre praticien référent.',
  ),
];

/// Parcours pédagogique + consentement éclairé obligatoire (RGPD / SaMD).
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _controller = PageController();
  int _index = 0;
  bool _consent = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  bool get _isLast => _index == _slides.length - 1;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DfScaffoldBackground(
        child: SafeArea(
          child: DfContentFrame(
            maxWidth: 720,
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('PODOTRACE', style: DfType.overline),
                    TextButton(
                      onPressed: () => _finish(skip: true),
                      child: Text('Passer',
                          style: DfType.caption
                              .copyWith(color: DfColors.creamDim)),
                    ),
                  ],
                ),
                Expanded(
                  child: PageView.builder(
                    controller: _controller,
                    onPageChanged: (i) => setState(() => _index = i),
                    itemCount: _slides.length,
                    itemBuilder: (context, i) => _SlideView(slide: _slides[i]),
                  ),
                ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: List.generate(_slides.length, (i) {
                    final active = i == _index;
                    return AnimatedContainer(
                      duration: const Duration(milliseconds: 260),
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      width: active ? 26 : 7,
                      height: 7,
                      decoration: BoxDecoration(
                        gradient: active ? DfGradients.copperSheen : null,
                        color: active ? null : DfColors.hairline,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    );
                  }),
                ),
                const SizedBox(height: 26),
                if (_isLast)
                  DfGlassCard(
                    padding: const EdgeInsets.all(18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('CONSENTEMENT ÉCLAIRÉ',
                            style: DfType.overline.copyWith(fontSize: 9)),
                        const SizedBox(height: 10),
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
                                  onChanged: (v) =>
                                      setState(() => _consent = v ?? false),
                                  side:
                                      const BorderSide(color: DfColors.copper),
                                  activeColor: DfColors.copper,
                                  checkColor: DfColors.ink,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  'Je comprends que PodoTrace est un outil '
                                  'd\'aide en phase de validation clinique. Il ne pose pas de '
                                  'diagnostic autonome et ne remplace pas une '
                                  'consultation. En cas d\'urgence, je contacte les '
                                  'secours (15 / 190). J\'accepte le traitement de mes '
                                  'données de santé chiffrées (RGPD / HDS).',
                                  style: DfType.caption.copyWith(height: 1.6),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 18),
                DfPrimaryButton(
                  label: _isLast ? 'Commencer' : 'Continuer',
                  icon: _isLast
                      ? Icons.check_rounded
                      : Icons.arrow_forward_rounded,
                  expand: true,
                  pulse: _isLast && _consent,
                  onPressed: _isLast
                      ? (_consent ? () => _finish() : null)
                      : () => _controller.nextPage(
                            duration: const Duration(milliseconds: 380),
                            curve: Curves.easeOutCubic,
                          ),
                ),
                const SizedBox(height: 14),
                const DfdDisclaimer(compact: true),
                const SizedBox(height: 10),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _finish({bool skip = false}) async {
    if (!skip && _isLast && !_consent) return;
    await context.read<AuthProvider>().markOnboardingDone();
  }
}

class _SlideView extends StatelessWidget {
  const _SlideView({required this.slide});

  final _OnboardingSlide slide;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 74,
          height: 74,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: DfColors.copper.withValues(alpha: 0.10),
            border: Border.all(color: DfColors.hairline),
          ),
          child: Icon(slide.icon, color: DfColors.copperLight, size: 30),
        ),
        const SizedBox(height: 30),
        Text(slide.overline.toUpperCase(), style: DfType.overline),
        const SizedBox(height: 14),
        Text(slide.title, style: DfType.display.copyWith(fontSize: 38)),
        const SizedBox(height: 18),
        Text(slide.body, style: DfType.body.copyWith(height: 1.7)),
      ],
    );
  }
}
