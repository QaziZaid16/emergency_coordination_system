import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

abstract final class OpsColors {
  static const ink = Color(0xFFE8EDF5);
  static const inkSoft = Color(0xFFBECADA);
  static const muted = Color(0xFF94A5BA);
  static const canvas = Color(0xFF0A101B);
  static const surface = Color(0xFF111D2D);
  static const surfaceRaised = Color(0xFF162438);
  static const line = Color(0xFF26384E);
  static const primary = Color(0xFF2583D2);
  static const primaryDark = Color(0xFF1C6FB7);
  static const primaryWash = Color(0xFF1A3551);
  static const accent = Color(0xFF6DB7FB);
  static const accentWash = Color(0xFF1A3551);
  static const success = Color(0xFF5DD2A9);
  static const successWash = Color(0xFF20382F);
  static const warning = Color(0xFFEFBA68);
  static const warningWash = Color(0xFF3A3224);
  static const critical = Color(0xFFF2777D);
  static const criticalWash = Color(0xFF40252B);
  static const blue = Color(0xFF6DB7FB);
  static const blueWash = Color(0xFF243247);
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
  static const double control = 14;
  static const double card = 18;
  static const double sheet = 24;
  static const double pill = 99;
}

abstract final class OpsTheme {
  static const systemOverlayStyle = SystemUiOverlayStyle(
    statusBarColor: OpsColors.canvas,
    statusBarIconBrightness: Brightness.light,
    statusBarBrightness: Brightness.dark,
    systemNavigationBarColor: OpsColors.canvas,
    systemNavigationBarIconBrightness: Brightness.light,
    systemNavigationBarDividerColor: OpsColors.line,
  );

  static ThemeData get dark {
    const scheme = ColorScheme.dark(
      primary: OpsColors.primary,
      onPrimary: Colors.white,
      secondary: OpsColors.success,
      onSecondary: Color(0xFF101A15),
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
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: OpsColors.canvas,
      canvasColor: OpsColors.surface,
      dialogTheme: DialogThemeData(
        backgroundColor: OpsColors.surfaceRaised,
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
        toolbarHeight: 68,
        systemOverlayStyle: systemOverlayStyle,
        titleSpacing: OpsSpace.lg,
        titleTextStyle: TextStyle(
          color: OpsColors.ink,
          fontSize: 18,
          fontWeight: FontWeight.w800,
          letterSpacing: -.25,
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
        fillColor: OpsColors.surfaceRaised,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: OpsSpace.lg,
          vertical: 15,
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
            fontWeight: FontWeight.w800,
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
            fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
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
          fontWeight: FontWeight.w800,
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
              ? OpsColors.primaryWash
              : OpsColors.surfaceRaised,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: OpsColors.surfaceRaised,
        contentTextStyle: const TextStyle(color: OpsColors.ink),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(OpsRadius.control),
          side: const BorderSide(color: OpsColors.line),
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
          fontWeight: FontWeight.w800,
          height: 1.12,
          letterSpacing: -.55,
        ),
        titleLarge: TextStyle(
          color: OpsColors.ink,
          fontSize: 20,
          fontWeight: FontWeight.w800,
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
