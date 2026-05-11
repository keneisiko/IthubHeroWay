export const IconHome = ({ active }: { active?: boolean }) => (
  <svg width="24" height="24" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M21.1962 9.62307C22.5778 8.64968 24.4222 8.64968 25.8038 9.62307L36.7569 17.3398C38.2022 18.3581 38.8076 20.2043 38.2459 21.8806L34.1129 34.2151C33.5666 35.8454 32.0396 36.9443 30.3202 36.9443H16.6798C14.9604 36.9443 13.4334 35.8454 12.8871 34.2151L8.75412 21.8806C8.19243 20.2043 8.79783 18.3581 10.2431 17.3398L21.1962 9.62307Z" fill={active ? 'white' : '#9A33F4'}/>
  </svg>
)

export const IconProfile = ({ active }: { active?: boolean }) => (
  <svg width="24" height="24" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M34.2565 28.7193C36.6943 30.7575 37.9133 31.7766 36.2394 36.3883C34.5655 41 31.7106 41 26.0008 41C24.7486 41 23.426 41 22.0012 41C16.2901 41 13.4345 41 11.7606 36.3883C10.0867 31.7766 11.3057 30.7575 13.7435 28.7193C16.5206 26.3974 20.0971 25 24 25C27.9029 25 31.4794 26.3974 34.2565 28.7193Z" fill={active ? 'white' : '#9A33F4'}/>
    <circle cx="24" cy="15" r="7" fill={active ? 'white' : '#9A33F4'}/>
  </svg>
)

export const IconQuests = ({ active }: { active?: boolean }) => (
  <svg width="24" height="24" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="18" y="10" width="22" height="5" rx="2.5" fill={active ? 'white' : '#9A33F4'}/>
    <rect x="18" y="21" width="22" height="5" rx="2.5" fill={active ? 'white' : '#9A33F4'}/>
    <rect x="18" y="32" width="22" height="5" rx="2.5" fill={active ? 'white' : '#9A33F4'}/>
    <circle cx="11.5" cy="23.5" r="3.5" fill={active ? 'white' : '#9A33F4'}/>
    <circle cx="11.5" cy="34.5" r="3.5" fill={active ? 'white' : '#9A33F4'}/>
    <circle cx="11.5" cy="12.5" r="3.5" fill={active ? 'white' : '#9A33F4'}/>
  </svg>
)

export const IconShop = ({ active }: { active?: boolean }) => (
  <svg width="24" height="24" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12.0883 24.2649L8.75497 14.2649C7.8916 11.6748 9.81947 9 12.5497 9H34.4503C37.1805 9 39.1084 11.6748 38.245 14.2649L34.9117 24.2649C34.3672 25.8983 32.8387 27 31.117 27H15.883C14.1613 27 12.6328 25.8983 12.0883 24.2649Z" fill={active ? 'white' : '#9A33F4'}/>
    <circle cx="15" cy="35" r="4" fill={active ? 'white' : '#9A33F4'}/>
    <circle cx="31" cy="35" r="4" fill={active ? 'white' : '#9A33F4'}/>
  </svg>
)

export const IconLeaders = ({ active }: { active?: boolean }) => (
  <svg width="24" height="24" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <g clipPath="url(#clip0)">
    <path d="M33.1022 36H14.8978C12.994 36 11.354 34.6581 10.977 32.792L8.19923 19.04C7.50367 15.5965 11.6132 13.2679 14.2097 15.6343L14.4733 15.8745C16.4557 17.6812 19.6514 16.6198 20.1589 13.9861C20.8781 10.2544 26.2428 10.3603 26.9243 14.099C27.4007 16.7126 30.5308 17.8583 32.5587 16.1421L33.2557 15.5522C36.1378 13.1132 40.4795 15.6798 39.732 19.3807L37.023 32.792C36.646 34.6581 35.006 36 33.1022 36Z" fill={active ? 'white' : '#9A33F4'}/>
    </g>
    <defs><clipPath id="clip0"><rect width="48" height="48" fill="white"/></clipPath></defs>
  </svg>
)

export const IconSquads = ({ active }: { active?: boolean }) => (
  <svg width="24" height="24" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M26.247 29.0155C27.729 30.0206 28.47 30.5232 27.1682 34.7616C25.8665 39 23.9117 39 20.0021 39C17.632 39 15.0498 39 12.001 39C8.08938 39 6.13354 39 4.83178 34.7616C3.53003 30.5232 4.27101 30.0206 5.75297 29.0155C8.5287 27.1328 12.1015 26 16 26C19.8985 26 23.4713 27.1328 26.247 29.0155Z" fill={active ? 'white' : '#9A33F4'}/>
    <path d="M42.247 29.0155C43.729 30.0206 44.47 30.5232 43.1682 34.7616C41.8665 39 39.9117 39 36.0021 39C33.632 39 31.0498 39 28.001 39C24.0894 39 22.1335 39 20.8318 34.7616C19.53 30.5232 20.271 30.0206 21.753 29.0155C24.5287 27.1328 28.1015 26 32 26C35.8985 26 39.4713 27.1328 42.247 29.0155Z" fill={active ? 'white' : '#9A33F4'}/>
    <circle cx="14" cy="16" r="7" fill={active ? 'white' : '#9A33F4'}/>
    <circle cx="32" cy="16" r="7" fill={active ? 'white' : '#9A33F4'}/>
  </svg>
)