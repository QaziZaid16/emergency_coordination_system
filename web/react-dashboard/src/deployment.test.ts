// @vitest-environment node
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const root = path.resolve(import.meta.dirname, '../../..');
const react = path.join(root, 'web/react-dashboard');
const vercel = JSON.parse(readFileSync(path.join(react, 'vercel.json'), 'utf8'));
const routeTarget = (route:string) => vercel.rewrites.find(({ source }:{source:string}) => source === route)?.destination;

describe('React website deployment configuration', () => {
  it('builds and publishes the React SPA relative to its configured Vercel root', () => {
    expect(vercel.installCommand).toBe('npm ci');
    expect(vercel.buildCommand).toBe('npm run build');
    expect(vercel.outputDirectory).toBe('dist');
    expect(existsSync(path.join(react, 'package-lock.json'))).toBe(true);
    expect(existsSync(path.join(react, 'index.html'))).toBe(true);
    const packageJson = JSON.parse(readFileSync(path.join(react, 'package.json'), 'utf8'));
    expect(packageJson.scripts.build).toBe('tsc -b && vite build');
    expect(packageJson.scripts.build).not.toContain('build_web_config.mjs');
    expect(existsSync(path.join(react, 'vercel.json'))).toBe(true);
  });

  it('rewrites dashboard and legacy invitation URLs to the React entry point', () => {
    expect(routeTarget('/admin')).toBe('/index.html');
    expect(routeTarget('/admin/')).toBe('/index.html');
    expect(routeTarget('/admin/:path*')).toBe('/index.html');
    expect(routeTarget('/activate')).toBe('/index.html');
    expect(routeTarget('/activate.html')).toBe('/index.html');
    const main = readFileSync(path.join(react, 'src/main.tsx'), 'utf8');
    expect(main).toMatch(/\['\/activate', '\/activate\.html'\]/);
    expect(main).toMatch(/takeInvitationToken/);
  });

  it('retains shared React assets and the Flutter Web source template', () => {
    expect(readFileSync(path.join(react, 'src/api/config.ts'), 'utf8')).toMatch(/VITE_ECS_API_ORIGIN/);
    const buildConfig=readFileSync(path.join(react, 'vite.config.ts'), 'utf8');
    expect(buildConfig).toMatch(/VITE_ECS_API_ORIGIN/);
    expect(buildConfig).toMatch(/VITE_ECS_ALLOW_UNCONFIGURED_BUILD/);
    expect(buildConfig).toMatch(/publicDir: '\.\.\/assets'/);
    expect(existsSync(path.join(root, 'web/index.html'))).toBe(true);
    expect(existsSync(path.join(root, 'web/manifest.json'))).toBe(true);
    expect(existsSync(path.join(root, 'web/assets/brand/official-logo.svg'))).toBe(true);
  });
});
