import 'package:flutter/foundation.dart';

/// Validates the public API origin supplied to a client build.
///
/// The API origin is public configuration, not a secret. Server credentials
/// must never be passed to the mobile or browser application.
class ApiConfiguration {
  ApiConfiguration(String value, {bool? releaseMode})
    : value = value.trim().replaceAll(RegExp(r'/+$'), ''),
      releaseMode = releaseMode ?? kReleaseMode;

  final String value;
  final bool releaseMode;

  String? get diagnostic {
    if (value.isEmpty) return 'API_BASE_URL is empty.';
    final uri = Uri.tryParse(value);
    if (uri == null || !uri.hasAuthority || uri.host.isEmpty) {
      return 'API_BASE_URL must be an absolute URL with a host.';
    }
    if (uri.userInfo.isNotEmpty ||
        uri.query.isNotEmpty ||
        uri.fragment.isNotEmpty) {
      return 'API_BASE_URL must contain only the service origin and optional path.';
    }
    final host = uri.host.toLowerCase();
    if (host.split('.').contains('your-api-host') ||
        (releaseMode && _isPlaceholder(host))) {
      return 'API_BASE_URL uses a placeholder host.';
    }
    if (releaseMode && uri.scheme != 'https') {
      return 'Release builds require an HTTPS API_BASE_URL.';
    }
    if (uri.scheme != 'https' &&
        !(uri.scheme == 'http' && !releaseMode && _isLocalHost(host))) {
      return 'Use HTTPS, or a loopback HTTP URL in a debug build.';
    }
    return null;
  }

  bool get isValid => diagnostic == null;

  static bool _isLocalHost(String host) =>
      host == 'localhost' ||
      host == '127.0.0.1' ||
      host == '::1' ||
      host == '10.0.2.2';

  static bool _isPlaceholder(String host) =>
      host == 'your-api-host' ||
      host == 'example.com' ||
      host == 'example.org' ||
      host == 'example.net' ||
      host.split('.').contains('example') ||
      host.endsWith('.test') ||
      host.endsWith('.invalid') ||
      host.endsWith('.localhost') ||
      host.endsWith('.example') ||
      host.endsWith('.example.test');
}
