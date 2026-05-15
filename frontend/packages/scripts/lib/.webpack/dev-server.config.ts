import { Configuration } from 'webpack-dev-server';

const backendTarget = process.env.MEDIACMS_BACKEND_URL || 'http://web:80';
const frontendPagePaths = new Set([
  '/',
  '/index',
  '/index.html',
  '/search',
  '/search.html',
  '/latest',
  '/latest.html',
  '/featured',
  '/featured.html',
  '/recommended',
  '/recommended.html',
  '/members',
  '/members.html',
  '/history',
  '/history.html',
  '/liked',
  '/liked.html',
  '/tags',
  '/tags.html',
  '/categories',
  '/categories.html',
  '/manage-media',
  '/manage-media.html',
  '/manage-users',
  '/manage-users.html',
  '/manage-comments',
  '/manage-comments.html',
  '/add-media',
  '/add-media.html',
  '/embed',
  '/embed.html',
  '/media',
  '/media.html',
  '/media-image',
  '/media-image.html',
  '/media-pdf',
  '/media-pdf.html',
  '/playlist',
  '/playlist.html',
  '/profile-media',
  '/profile-media.html',
  '/profile-about',
  '/profile-about.html',
  '/profile-playlists',
  '/profile-playlists.html',
  '/profile-shared-by-me',
  '/profile-shared-by-me.html',
  '/profile-shared-with-me',
  '/profile-shared-with-me.html',
  '/about',
  '/about.html',
  '/terms',
  '/terms.html',
  '/contact',
  '/contact.html',
  '/signin',
  '/signin.html',
  '/signout',
  '/signout.html',
  '/register',
  '/register.html',
  '/reset-password',
  '/reset-password.html',
  '/edit-media',
  '/edit-media.html',
  '/edit-channel',
  '/edit-channel.html',
  '/edit-profile',
  '/edit-profile.html',
]);
const frontendAssetPattern = /\.(js|css|json|map|png|jpe?g|gif|svg|ico|webp|woff2?|ttf|eot)$/;

function shouldProxyToBackend(pathname: string, req: { method?: string }): boolean {
  const method = (req.method || 'GET').toUpperCase();

  if (method !== 'GET' && method !== 'HEAD') {
    return true;
  }

  if (pathname.startsWith('/sockjs-node') || pathname.startsWith('/webpack-dev-server')) {
    return false;
  }

  if (frontendPagePaths.has(pathname) || frontendAssetPattern.test(pathname)) {
    return false;
  }

  return true;
}

export function configFunc(contentBase: string): Configuration {
  return {
    watchOptions: {
      poll: true,
    },
    contentBase: contentBase,
    compress: true,
    hot: true,
    proxy: [
      {
        context: shouldProxyToBackend,
        target: backendTarget,
        changeOrigin: true,
      },
    ],
  };
}
