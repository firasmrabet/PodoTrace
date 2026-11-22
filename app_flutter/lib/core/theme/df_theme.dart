import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Palette « Sérénité » : papier chaud, sauge clinique, encre végétale.
/// Chaque couleur porte un rôle sémantique strict (aucune couleur décorative
/// ne doit être utilisée pour coder une information médicale). Alignée sur
/// `web/css/app.css` (tokens `--paper`, `--sage`, `--ink`…).
class DfColors {
  DfColors._();

  // Fond
  static const ink = Color(0xFFF4F2EC);
  static const plum = Color(0xFFFFFFFF);
  static const plumSoft = Color(0xFFFBFAF6);
  static const plumLift = Color(0xFFEFECE3);

  // Métal chaud
  static const copper = Color(0xFF5C8570);
  static const copperLight = Color(0xFF7EA48D);
  static const copperDeep = Color(0xFF3F6152);
  static const champagne = Color(0xFFE8DCC6);

  // Neutres chauds
  static const cream = Color(0xFF16302B);
  static const creamDim = Color(0xFF3C4F4A);
  static const muted = Color(0xFF5E736B);
  static const hairline = Color(0x1A16302B);

  // Sémantique clinique
  static const stable = Color(0xFF5C8570);
  static const moderate = Color(0xFFB98C3C);
  static const critical = Color(0xFFA9535C);
  static const info = Color(0xFF6F93B0);

  // Tissus (aligné sur le backend)
  static const tissueNecrosis = Color(0xFF3A4340);
  static const tissueFibrin = Color(0xFFE8DCC6);
  static const tissueGranulation = Color(0xFFA9535C);
  static const tissueEpithelial = Color(0xFFE3B7B8);

  /// Couleur associée à un niveau de risque (`low` / `moderate` / `high`).
  static Color forRisk(String? level) {
    switch (level) {
      case 'high':
        return critical;
      case 'moderate':
        return moderate;
      default:
        return stable;
    }
  }

  static Color forStatus(String? status) {
    switch (status) {
      case 'alert':
        return critical;
      case 'improving':
        return stable;
      case 'stable':
        return moderate;
      default:
        return muted;
    }
  }
}

/// Dégradés signature.
class DfGradients {
  DfGradients._();

  static const copperSheen = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF7EA48D), Color(0xFF5C8570), Color(0xFF3F6152)],
  );

  static const glass = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFFFFFFF), Color(0x00FFFFFF)],
  );

  static const plumVeil = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0xFFF7F5EF), Color(0xFFF4F2EC)],
  );

  static const aurora = RadialGradient(
    center: Alignment(-0.6, -0.8),
    radius: 1.6,
    colors: [Color(0x145C8570), Color(0x00000000)],
  );

  static LinearGradient risk(String level) => LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [
          DfColors.forRisk(level).withValues(alpha: 0.85),
          DfColors.forRisk(level)
        ],
      );
}

/// Typographie : serif doux pour les titres, Inter pour les données.
class DfType {
  DfType._();

  static TextStyle get display => GoogleFonts.fraunces(
        fontSize: 40,
        height: 1.05,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.5,
        color: DfColors.cream,
      );

  static TextStyle get h1 => GoogleFonts.fraunces(
        fontSize: 30,
        height: 1.12,
        fontWeight: FontWeight.w600,
        color: DfColors.cream,
      );

  static TextStyle get h2 => GoogleFonts.fraunces(
        fontSize: 23,
        height: 1.2,
        fontWeight: FontWeight.w600,
        color: DfColors.cream,
      );

  static TextStyle get h3 => GoogleFonts.fraunces(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        color: DfColors.cream,
      );

  static TextStyle get body => GoogleFonts.inter(
        fontSize: 14,
        height: 1.55,
        color: DfColors.creamDim,
      );

  static TextStyle get bodyStrong => GoogleFonts.inter(
        fontSize: 14,
        height: 1.45,
        fontWeight: FontWeight.w600,
        color: DfColors.cream,
      );

  static TextStyle get caption => GoogleFonts.inter(
        fontSize: 11.5,
        height: 1.4,
        color: DfColors.muted,
      );

  static TextStyle get overline => GoogleFonts.inter(
        fontSize: 10,
        height: 1.2,
        fontWeight: FontWeight.w600,
        letterSpacing: 2.4,
        color: DfColors.copper,
      );

  static TextStyle get metric => GoogleFonts.fraunces(
        fontSize: 34,
        height: 1,
        fontWeight: FontWeight.w600,
        color: DfColors.cream,
      );

  static TextStyle get metricSmall => GoogleFonts.fraunces(
        fontSize: 22,
        height: 1,
        fontWeight: FontWeight.w600,
        color: DfColors.cream,
      );
}

class DfTheme {
  DfTheme._();

  static ThemeData build() {
    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: DfColors.ink,
      canvasColor: DfColors.ink,
      colorScheme: const ColorScheme.light(
        primary: DfColors.copper,
        onPrimary: Color(0xFFFFFFFF),
        secondary: DfColors.copperLight,
        onSecondary: Color(0xFFFFFFFF),
        surface: DfColors.plum,
        onSurface: DfColors.cream,
        error: DfColors.critical,
        onError: Color(0xFFFFFFFF),
      ),
      textTheme: base.textTheme.copyWith(
        displayLarge: DfType.display,
        headlineLarge: DfType.h1,
        headlineMedium: DfType.h2,
        titleMedium: DfType.h3,
        bodyMedium: DfType.body,
        labelSmall: DfType.overline,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: DfType.h2,
        iconTheme: const IconThemeData(color: DfColors.creamDim),
      ),
      dividerTheme: const DividerThemeData(
        color: DfColors.hairline,
        thickness: 0.8,
        space: 28,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFFFBFAF6),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        hintStyle: DfType.caption,
        labelStyle: DfType.caption.copyWith(color: DfColors.creamDim),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: DfColors.hairline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: DfColors.hairline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: DfColors.copper, width: 1.4),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: DfColors.critical),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: DfColors.copper,
          foregroundColor: DfColors.ink,
          padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 18),
          textStyle: GoogleFonts.inter(
            fontSize: 13.5,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.4,
          ),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: DfColors.copperDeep,
          side: const BorderSide(color: DfColors.hairline),
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: DfColors.copperDeep),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: DfColors.plum,
        indicatorColor: DfColors.copper.withValues(alpha: 0.18),
        labelTextStyle: WidgetStatePropertyAll(
          GoogleFonts.inter(fontSize: 10.5, letterSpacing: 0.4),
        ),
        iconTheme: const WidgetStatePropertyAll(
          IconThemeData(color: DfColors.creamDim, size: 22),
        ),
        height: 68,
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: DfColors.plum,
        indicatorColor: DfColors.copper.withValues(alpha: 0.16),
        selectedIconTheme:
            const IconThemeData(color: DfColors.copper, size: 24),
        unselectedIconTheme:
            const IconThemeData(color: DfColors.muted, size: 22),
        selectedLabelTextStyle: GoogleFonts.inter(
          fontSize: 11.5,
          color: DfColors.copperDeep,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelTextStyle: GoogleFonts.inter(
          fontSize: 11.5,
          color: DfColors.muted,
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: const Color(0xFFF7F5EF),
        side: const BorderSide(color: DfColors.hairline),
        labelStyle: DfType.caption.copyWith(color: DfColors.creamDim),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(30)),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: DfColors.copperDeep,
        contentTextStyle: DfType.body,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      sliderTheme: const SliderThemeData(
        activeTrackColor: DfColors.copper,
        inactiveTrackColor: DfColors.hairline,
        thumbColor: DfColors.copperLight,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: DfColors.copper,
      ),
    );
  }
}
