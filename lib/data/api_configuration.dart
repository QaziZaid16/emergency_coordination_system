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
        !(uri.scheme == 'http' &&
            !releaseMode &&
            (_isLocalHost(host) ||
                _isPrivateIpv4(host) ||
                _isUniqueLocalIpv6(host)))) {
      return 'Use HTTPS, or a private-network HTTP URL in a debug build.';
    }
    return null;
  }

  bool get isValid => diagnostic == null;

  static bool _isLocalHost(String host) =>
      host == 'localhost' ||
      host == '127.0.0.1' ||
      host == '::1' ||
      host == '10.0.2.2';

  static bool _isPrivateIpv4(String host) {
    final parts = host.split('.');
    if (parts.length != 4) return false;
    final octets = <int>[];
    for (final part in parts) {
      final value = int.tryParse(part);
      if (value == null ||
          value < 0 ||
          value > 255 ||
          part != value.toString()) {
        return false;
      }
      octets.add(value);
    }
    return octets[0] == 10 ||
        (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31) ||
        (octets[0] == 192 && octets[1] == 168);
  }

  static bool _isUniqueLocalIpv6(String host) {
    // fc00::/7 is IPv6 unique-local space. Link-local IPv6 is excluded because
    // a usable URL also needs an interface scope identifier.
    final firstHextet = host.split(':').first;
    if (firstHextet.isEmpty) return false;
    final value = int.tryParse(firstHextet, radix: 16);
    return value != null && value >= 0xfc00 && value <= 0xfdff;
  }

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
