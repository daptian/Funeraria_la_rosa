module.exports = {
  content: [
    '../templates/**/*.html',
    '../**/templates/**/*.html',
  ],
  theme: {
    extend: {
      keyframes : {
        fadeOutUp : {
          '0%' : {transform: 'translateY(0)', opacity: '1'},
          '100%' : {transform: 'translateY(-25px)'}
        }
      },
      animation : {
        'fadeOutUp' : 'fadeOutUp 0.5s cubic-bezier(0.4, 0, 0.2, 1) forwards',
      },
      colors: {
        'dark-brown': '#1d1411',
        'gold': '#d4af37',
      },
      backgroundColor: {
        'dark-brown': '#1d1411',
      }
    },
    fontFamily:{
      sans: ['Inter', 'sans-serif'],
    }
  },
  plugins: [],
}