import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'dart:io';

import 'package:flutter/services.dart';

import 'data/api_client.dart';
import 'data/operations_store.dart';
import 'presentation/design_system.dart';
import 'presentation/portals.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(OpsTheme.systemOverlayStyle);
  OperationsStore? trainingStore;
  if (kDebugMode && const bool.fromEnvironment('ENABLE_TRAINING_WORKSPACE')) {
    const storageChannel = MethodChannel(
      'edu.cgc.university.emergency_coordination_system/storage',
    );
    final directory = await storageChannel.invokeMethod<String>(
      'getFilesDirectory',
    );
    if (directory == null) {
      throw StateError('Android app storage is unavailable.');
    }
    trainingStore = OperationsStore(
      File('$directory/emergency_workspace.json'),
    );
    await trainingStore.load();
  }
  runApp(EmergencyCoordinationApp(trainingStore: trainingStore));
}

class EmergencyCoordinationApp extends StatelessWidget {
  const EmergencyCoordinationApp({super.key, this.trainingStore});
  final OperationsStore? trainingStore;
  static final api = ApiClient();
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'IERCS',
    debugShowCheckedModeBanner: false,
    theme: OpsTheme.light,
    home: PortalEntryPage(api: api, trainingStore: trainingStore),
  );
}
