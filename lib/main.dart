import 'package:flutter/material.dart';

import 'dart:io';

import 'package:flutter/services.dart';

import 'data/api_client.dart';
import 'data/operations_store.dart';
import 'presentation/design_system.dart';
import 'presentation/portals.dart';

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
  static final api = ApiClient();
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Emergency Coordination',
    debugShowCheckedModeBanner: false,
    theme: OpsTheme.light,
    home: PortalEntryPage(api: api, trainingStore: store),
  );
}
