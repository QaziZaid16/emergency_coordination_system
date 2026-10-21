import 'package:flutter/material.dart';

import 'dart:io';

import 'package:flutter/services.dart';

import 'data/operations_store.dart';
import 'presentation/home_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  const storageChannel = MethodChannel(
    'edu.cgc.university.emergency_coordination_system/storage',
  );
  final directory = await storageChannel.invokeMethod<String>(
    'getFilesDirectory',
  );
  if (directory == null) {
    throw StateError('Android app storage is unavailable.');
  }
  final store = OperationsStore(File('$directory/emergency_workspace.json'));
  await store.load();
  runApp(EmergencyCoordinationApp(store: store));
}

class EmergencyCoordinationApp extends StatelessWidget {
  const EmergencyCoordinationApp({super.key, required this.store});
  final OperationsStore store;
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Emergency Coordination',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFFB64032),
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: const Color(0xFFF6F7F9),
      cardTheme: const CardThemeData(
        color: Colors.white,
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        filled: true,
        fillColor: Colors.white,
      ),
    ),
    home: HomePage(store: store),
  );
}
