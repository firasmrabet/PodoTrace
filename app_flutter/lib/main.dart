import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/config/app_config.dart';
import 'core/theme/df_theme.dart';
import 'data/services/api_service.dart';
import 'features/auth/auth_flow.dart';
import 'features/onboarding/onboarding_screen.dart';
import 'features/shell/app_shell.dart';
import 'features/splash/splash_screen.dart';
import 'state/app_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const DiaFootApp());
}

class DiaFootApp extends StatelessWidget {
  const DiaFootApp({super.key});

  @override
  Widget build(BuildContext context) {
    final api = ApiService();
    return MultiProvider(
      providers: [
        Provider<ApiService>.value(value: api),
        ChangeNotifierProvider(create: (_) => LocaleProvider()),
        ChangeNotifierProvider(create: (_) => AuthProvider(api)),
        ChangeNotifierProvider(create: (_) => WoundProvider(api)),
      ],
      child: Consumer<LocaleProvider>(
        builder: (context, locale, _) => MaterialApp(
          title: AppConfig.appName,
          debugShowCheckedModeBanner: false,
          theme: DfTheme.build(),
          locale: Locale(locale.locale),
          supportedLocales: const [Locale('fr'), Locale('en')],
          localizationsDelegates: const [
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          builder: (context, child) => MediaQuery.withClampedTextScaling(
            minScaleFactor: 0.9,
            maxScaleFactor: 1.25,
            child: child ?? const SizedBox.shrink(),
          ),
          home: const RootGate(),
        ),
      ),
    );
  }
}

/// Aiguillage racine : splash → onboarding/auth → coque applicative.
class RootGate extends StatefulWidget {
  const RootGate({super.key});

  @override
  State<RootGate> createState() => _RootGateState();
}

class _RootGateState extends State<RootGate> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AuthProvider>().bootstrap();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        switch (auth.status) {
          case SessionStatus.checking:
            return const SplashScreen();
          case SessionStatus.unauthenticated:
          case SessionStatus.pendingOtp:
            return const AuthFlow();
          case SessionStatus.authenticated:
            if (auth.user?.onboardingDone == false) {
              return const OnboardingScreen();
            }
            return const AppShell();
        }
      },
    );
  }
}
