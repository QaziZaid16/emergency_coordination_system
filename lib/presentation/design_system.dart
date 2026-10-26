import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Mobile tokens for the shared IERCS navy/cyan identity and neutral surfaces.
abstract final class OpsColors {
  static const ink = Color(0xFF191A18);
  static const inkSoft = Color(0xFF45463F);
  static const muted = Color(0xFF777870);
  static const canvas = Color(0xFFEFEEE9);
  static const surface = Color(0xFFFFFFFF);
  static const surfaceRaised = Color(0xFFF6F5F1);
  static const line = Color(0xFFE6E3DC);
  static const primary = Color(0xFF071A36);
  static const primaryDark = Color(0xFF06142B);
  static const primaryWash = Color(0xFFE3F7FC);
  static const accent = Color(0xFF007A9B);
  static const accentWash = Color(0xFFDFF7FF);
  static const success = Color(0xFF2D7953);
  static const successWash = Color(0xFFEAF3E8);
  static const warning = Color(0xFFA46D19);
  static const warningWash = Color(0xFFFBF2D9);
  static const critical = Color(0xFFD92D3F);
  static const criticalWash = Color(0xFFFFF0ED);
  static const blue = Color(0xFF007A9B);
  static const blueWash = Color(0xFFEAF9FD);
}

abstract final class OpsSpace {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double contentMax = 860;
}

abstract final class OpsRadius {
  static const double control = 10;
  static const double card = 15;
  static const double sheet = 22;
  static const double pill = 99;
}

abstract final class OpsTheme {
  static const systemOverlayStyle = SystemUiOverlayStyle(
    statusBarColor: OpsColors.canvas,
    statusBarIconBrightness: Brightness.dark,
    statusBarBrightness: Brightness.light,
    systemNavigationBarColor: OpsColors.surface,
    systemNavigationBarIconBrightness: Brightness.dark,
    systemNavigationBarDividerColor: OpsColors.line,
  );

  static ThemeData get light {
    const scheme = ColorScheme.light(
      primary: OpsColors.primary,
      onPrimary: Colors.white,
      secondary: OpsColors.accent,
      onSecondary: OpsColors.ink,
      error: OpsColors.critical,
      onError: Colors.white,
      surface: OpsColors.surface,
      onSurface: OpsColors.ink,
      surfaceContainerHighest: OpsColors.surfaceRaised,
      outline: OpsColors.line,
      outlineVariant: OpsColors.line,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: scheme,
      scaffoldBackgroundColor: OpsColors.canvas,
      canvasColor: OpsColors.surface,
      dialogTheme: DialogThemeData(
        backgroundColor: OpsColors.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(OpsRadius.sheet),
          side: const BorderSide(color: OpsColors.line),
        ),
      ),
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: OpsColors.surface,
        modalBackgroundColor: OpsColors.surface,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        dragHandleColor: OpsColors.muted,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: OpsColors.canvas,
        foregroundColor: OpsColors.ink,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        toolbarHeight: 64,
        systemOverlayStyle: systemOverlayStyle,
        titleSpacing: OpsSpace.lg,
        titleTextStyle: TextStyle(
          color: OpsColors.ink,
          fontSize: 19,
          fontWeight: FontWeight.w700,
          letterSpacing: -.3,
        ),
      ),
      cardTheme: CardThemeData(
        color: OpsColors.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(OpsRadius.card),
          side: const BorderSide(color: OpsColors.line),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(OpsRadius.control),
          borderSide: const BorderSide(color: OpsColors.line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(OpsRadius.control),
          borderSide: const BorderSide(color: OpsColors.line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(OpsRadius.control),
          borderSide: const BorderSide(color: OpsColors.primary, width: 1.5),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(OpsRadius.control),
          borderSide: const BorderSide(color: OpsColors.critical),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(OpsRadius.control),
          borderSide: const BorderSide(color: OpsColors.critical, width: 1.5),
        ),
        filled: true,
        fillColor: OpsColors.surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: OpsSpace.lg,
          vertical: 14,
        ),
        labelStyle: const TextStyle(color: OpsColors.muted),
        hintStyle: const TextStyle(color: OpsColors.muted),
        prefixIconColor: OpsColors.muted,
        suffixIconColor: OpsColors.muted,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          backgroundColor: OpsColors.primary,
          foregroundColor: Colors.white,
          disabledBackgroundColor: OpsColors.surfaceRaised,
          disabledForegroundColor: OpsColors.muted,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(OpsRadius.control),
          ),
          textStyle: const TextStyle(
            fontWeight: FontWeight.w700,
            letterSpacing: .1,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(44, 44),
          foregroundColor: OpsColors.ink,
          side: const BorderSide(color: OpsColors.line),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(OpsRadius.control),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: OpsColors.primary,
          minimumSize: const Size(44, 44),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 76,
        backgroundColor: OpsColors.surface,
        indicatorColor: OpsColors.primaryWash,
        surfaceTintColor: Colors.transparent,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return TextStyle(
            fontSize: 10,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            color: selected ? OpsColors.primary : OpsColors.muted,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return IconThemeData(
            color: selected ? OpsColors.primary : OpsColors.muted,
            size: 22,
          );
        }),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: OpsColors.surfaceRaised,
        selectedColor: OpsColors.primaryWash,
        side: const BorderSide(color: OpsColors.line),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(OpsRadius.pill),
        ),
        labelStyle: const TextStyle(color: OpsColors.inkSoft),
        secondaryLabelStyle: const TextStyle(
          color: OpsColors.primary,
          fontWeight: FontWeight.w700,
        ),
      ),
      dividerColor: OpsColors.line,
      listTileTheme: const ListTileThemeData(
        iconColor: OpsColors.muted,
        textColor: OpsColors.ink,
        tileColor: Colors.transparent,
        contentPadding: EdgeInsets.symmetric(horizontal: OpsSpace.lg),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? OpsColors.primary
              : OpsColors.muted,
        ),
        trackColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.selected)
              ? OpsColors.accent
              : OpsColors.surfaceRaised,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: OpsColors.ink,
        contentTextStyle: const TextStyle(color: Colors.white),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(OpsRadius.control),
        ),
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: OpsColors.primary,
        linearTrackColor: OpsColors.surfaceRaised,
      ),
      textTheme: const TextTheme(
        headlineSmall: TextStyle(
          color: OpsColors.ink,
          fontSize: 25,
          fontWeight: FontWeight.w700,
          height: 1.12,
          letterSpacing: -.55,
        ),
        titleLarge: TextStyle(
          color: OpsColors.ink,
          fontSize: 20,
          fontWeight: FontWeight.w700,
          letterSpacing: -.3,
        ),
        titleMedium: TextStyle(
          color: OpsColors.ink,
          fontSize: 16,
          fontWeight: FontWeight.w700,
        ),
        bodyLarge: TextStyle(color: OpsColors.ink, fontSize: 15, height: 1.4),
        bodyMedium: TextStyle(
          color: OpsColors.inkSoft,
          fontSize: 13,
          height: 1.4,
        ),
        bodySmall: TextStyle(color: OpsColors.muted, fontSize: 11, height: 1.4),
        labelLarge: TextStyle(
          color: OpsColors.ink,
          fontSize: 13,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
