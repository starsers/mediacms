import React from 'react';

export const Logo = ({ loading = 'lazy', title, alt, href = '#' }) => {
  return (
    <div className="logo">
      <a href={href} title={title}>
        <div className="logo-wrapper" data-v-79554b65="">
          <img
            src="https://static.worldaic.com.cn/IMAGE2024/2025-02-18/0d86a1edd1e24a9e8068303bc555f683.png"
            alt={alt || 'EY Logo'}
            title={title}
            loading={loading}
            className="logo-image"
            data-v-79554b65=""
          />
        </div>
      </a>
    </div>
  );
};
