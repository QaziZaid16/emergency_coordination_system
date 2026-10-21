import 'package:flutter/material.dart';

abstract final class OpsColors {
  static const ink = Color(0xFF17313E);
  static const inkSoft = Color(0xFF415D69);
  static const muted = Color(0xFF748792);
  static const canvas = Color(0xFFF2F6F6);
  static const surface = Color(0xFFFFFFFF);
  static const line = Color(0xFFDCE7E8);
  static const primary = Color(0xFF126D67);
  static const primaryDark = Color(0xFF0E514E);
  static const primaryWash = Color(0xFFE4F2F0);
  static const accent = Color(0xFFE06B58);
  static const accentWash = Color(0xFFFFEEE9);
  static const success = Color(0xFF28795D);
  static const warning = Color(0xFFAD7411);
  static const critical = Color(0xFFB42318);
  static const blue = Color(0xFF3569A8);
}

abstract final class OpsTheme {
  static ThemeData get light {
    final scheme = const ColorScheme.light(
      primary: OpsColors.primary,
      onPrimary: Colors.white,
      secondary: OpsColors.accent,
      onSecondary: Colors.white,
      error: OpsColors.critical,
      onError: Colors.white,
      surface: OpsColors.surface,
      onSurface: OpsColors.ink,
      outline: OpsColors.line,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: OpsColors.canvas,
      appBarTheme: const AppBarTheme(
        backgroundColor: OpsColors.canvas,
        foregroundColor: OpsColors.ink,
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        toolbarHeight: 72,
        titleSpacing: 20,
        titleTextStyle: TextStyle(
          color: OpsColors.ink,
          fontSize: 19,
          fontWeight: FontWeight.w800,
        ),
      ),
      cardTheme: CardThemeData(
        color: OpsColors.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: const BorderSide(color: OpsColors.line),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: OpsColors.line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: OpsColors.line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: OpsColors.primary, width: 1.6),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: OpsColors.critical),
        ),
        filled: true,
        fillColor: OpsColors.surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 15,
          vertical: 14,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(44, 44),
          foregroundColor: OpsColors.primary,
          side: const BorderSide(color: OpsColors.line),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 76,
        backgroundColor: OpsColors.surface,
        indicatorColor: OpsColors.primaryWash,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return TextStyle(
            fontSize: 11,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            color: selected ? OpsColors.primaryDark : OpsColors.muted,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return IconThemeData(
            color: selected ? OpsColors.primaryDark : OpsColors.muted,
            size: 22,
          );
        }),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: OpsColors.surface,
        selectedColor: OpsColors.primaryWash,
        side: const BorderSide(color: OpsColors.line),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        labelStyle: const TextStyle(color: OpsColors.inkSoft),
        secondaryLabelStyle: const TextStyle(
          color: OpsColors.primaryDark,
          fontWeight: FontWeight.w700,
        ),
      ),
      dividerColor: OpsColors.line,
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      textTheme: const TextTheme(
        headlineSmall: TextStyle(
          color: OpsColors.ink,
          fontSize: 25,
          fontWeight: FontWeight.w800,
          height: 1.12,
        ),
        titleLarge: TextStyle(
          color: OpsColors.ink,
          fontSize: 20,
          fontWeight: FontWeight.w800,
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
      ),
    );
  }
}
