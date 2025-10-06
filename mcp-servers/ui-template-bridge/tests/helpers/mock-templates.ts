import { registerMockTemplate, unregisterMockTemplate, clearMockTemplates } from './mock-fixture.js';

/**
 * Next.js App Router Template Fixture
 * Tests: dependency chains, @/ aliases, asset imports
 */
export const NEXT_APP_ROUTER_FIXTURE = {
  'src/components/Button.tsx': `import { Icon } from './Icon';

export interface ButtonProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary';
  onClick?: () => void;
}

export const Button: React.FC<ButtonProps> = ({ children, variant = 'primary', onClick }) => {
  return (
    <button className={\`btn btn-\${variant}\`} onClick={onClick}>
      <Icon name="arrow" />
      {children}
    </button>
  );
};`,

  'src/components/Icon.tsx': `import { getIconPath } from '@/lib/utils';

export interface IconProps {
  name: string;
  size?: number;
}

export const Icon: React.FC<IconProps> = ({ name, size = 24 }) => {
  const path = getIconPath(name);
  return <svg width={size} height={size}><use href={path} /></svg>;
};`,

  'src/components/Card.tsx': `import cardImage from '@/assets/card.jpg';

export interface CardProps {
  title: string;
  content: string;
}

export const Card: React.FC<CardProps> = ({ title, content }) => {
  return (
    <div className="card">
      <img src={cardImage} alt="Card background" />
      <h2>{title}</h2>
      <p>{content}</p>
    </div>
  );
};`,

  'src/components/Input.tsx': `import { Button } from './Button';

export interface InputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export const Input: React.FC<InputProps> = ({ value, onChange, placeholder }) => {
  return (
    <div className="input-group">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      <Button variant="secondary">Submit</Button>
    </div>
  );
};`,

  'src/components/hero.tsx': `import { Button } from './Button';

export const Hero = () => (
  <div className="hero">
    <h1>Welcome</h1>
    <Button variant="primary">Get Started</Button>
  </div>
);`,

  'src/components/features.tsx': `export const Features = () => (
  <div className="features">
    <h2>Features</h2>
    <ul>
      <li>Fast</li>
      <li>Reliable</li>
      <li>Scalable</li>
    </ul>
  </div>
);`,

  'src/lib/utils.ts': `export function getIconPath(name: string): string {
  return \`/icons/\${name}.svg\`;
}

export function formatDate(date: Date): string {
  return date.toLocaleDateString();
}

export function cn(...classes: string[]): string {
  return classes.filter(Boolean).join(' ');
}`,

  'src/assets/card.jpg': '// Mock JPEG binary data (base64)\n// /9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgICAgMCAgI=',

  'src/assets/icon.svg': `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <path d="M12 2L2 7v10c0 5.5 3.8 10.7 10 12 6.2-1.3 10-6.5 10-12V7l-10-5z"/>
</svg>`,

  'src/styles/globals.css': `.btn {
  padding: 0.5rem 1rem;
  border-radius: 0.25rem;
  border: none;
  cursor: pointer;
}

.btn-primary {
  background-color: #0070f3;
  color: white;
}

.btn-secondary {
  background-color: #666;
  color: white;
}

.card {
  border: 1px solid #eaeaea;
  border-radius: 0.5rem;
  padding: 1rem;
}`,

  'tsconfig.json': `{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM"],
    "jsx": "react",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "allowJs": true,
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules"]
}`,

  'package.json': `{
  "name": "next-app-router-template",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "next": "^14.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0"
  }
}`
};

/**
 * React + Vite Template Fixture
 * Tests: simpler dependency chains, different aliases
 */
export const REACT_VITE_FIXTURE = {
  'src/components/Button.tsx': `import { Icon } from './Icon';

export interface ButtonProps {
  label: string;
  type?: 'button' | 'submit';
}

export const Button: React.FC<ButtonProps> = ({ label, type = 'button' }) => {
  return (
    <button type={type}>
      <Icon />
      {label}
    </button>
  );
};`,

  'src/components/Icon.tsx': `import { getIconUrl } from '$/utils';

export const Icon: React.FC = () => {
  const url = getIconUrl();
  return <img src={url} alt="icon" />;
};`,

  'src/components/Card.tsx': `import bgImage from '$/assets/background.jpg';

export interface CardProps {
  heading: string;
}

export const Card: React.FC<CardProps> = ({ heading }) => {
  return (
    <div style={{ backgroundImage: \`url(\${bgImage})\` }}>
      <h3>{heading}</h3>
    </div>
  );
};`,

  'src/components/Input.tsx': `import { Button } from './Button';

export interface InputProps {
  name: string;
}

export const Input: React.FC<InputProps> = ({ name }) => {
  return (
    <div>
      <input name={name} />
      <Button label="Go" />
    </div>
  );
};`,

  'src/utils.ts': `export function getIconUrl(): string {
  return '/icon.png';
}`,

  'src/assets/background.jpg': '// Mock JPEG binary\n// /9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgICAgMCAgI=',

  'src/assets/logo.svg': `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="40" fill="#61dafb"/>
</svg>`,

  'src/main.css': `body {
  font-family: sans-serif;
  margin: 0;
  padding: 1rem;
}

button {
  background: #646cff;
  color: white;
  border: none;
  padding: 0.6rem 1.2rem;
  cursor: pointer;
}`,

  'tsconfig.json': `{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "baseUrl": ".",
    "paths": {
      "$/*": ["./src/*"]
    }
  },
  "include": ["src"]
}`,

  'package.json': `{
  "name": "react-vite-template",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0"
  }
}`
};

/**
 * Vue + Vite Template Fixture
 * Tests: .vue files, different import syntax
 */
export const VUE_VITE_FIXTURE = {
  'src/components/Button.vue': `<template>
  <button :class="buttonClass" @click="handleClick">
    <Icon />
    <slot></slot>
  </button>
</template>

<script setup lang="ts">
import Icon from './Icon.vue';

interface Props {
  variant?: 'primary' | 'danger';
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary'
});

const buttonClass = computed(() => \`btn-\${props.variant}\`);

const emit = defineEmits<{
  click: []
}>();

function handleClick() {
  emit('click');
}
</script>`,

  'src/components/Icon.vue': `<template>
  <svg class="icon">
    <use :href="iconPath" />
  </svg>
</template>

<script setup lang="ts">
import { getIconPath } from '~/utils';

const iconPath = getIconPath('default');
</script>`,

  'src/components/Card.vue': `<template>
  <div class="card" :style="cardStyle">
    <h2>{{ title }}</h2>
  </div>
</template>

<script setup lang="ts">
import cardBg from '~/assets/card-bg.jpg';

interface Props {
  title: string;
}

const props = defineProps<Props>();

const cardStyle = {
  backgroundImage: \`url(\${cardBg})\`
};
</script>`,

  'src/components/Input.vue': `<template>
  <div class="input-wrapper">
    <input v-model="localValue" />
    <Button @click="handleSubmit">Send</Button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Button from './Button.vue';

const localValue = ref('');

function handleSubmit() {
  console.log(localValue.value);
}
</script>`,

  'src/utils.ts': `export function getIconPath(name: string): string {
  return \`#icon-\${name}\`;
}`,

  'src/assets/card-bg.jpg': '// Mock JPEG\n// /9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAMCAgICAgMCAgI=',

  'src/assets/sprite.svg': `<svg xmlns="http://www.w3.org/2000/svg">
  <symbol id="icon-default" viewBox="0 0 24 24">
    <path d="M12 2L2 12h3v8h14v-8h3L12 2z"/>
  </symbol>
</svg>`,

  'src/style.css': `.btn-primary {
  background: #42b883;
  color: white;
}

.btn-danger {
  background: #f56c6c;
  color: white;
}

.card {
  padding: 1rem;
  border-radius: 8px;
}`,

  'tsconfig.json': `{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "baseUrl": ".",
    "paths": {
      "~/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.vue"]
}`,

  'package.json': `{
  "name": "vue-vite-template",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "vue": "^3.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^4.0.0",
    "typescript": "^5.0.0",
    "vite": "^5.0.0"
  }
}`
};

/**
 * Sets up all mock fixtures for testing
 * Call in beforeAll() or beforeEach()
 */
export async function setupAllFixtures(): Promise<void> {
  await registerMockTemplate('next-app-router', NEXT_APP_ROUTER_FIXTURE);
  await registerMockTemplate('react-vite', REACT_VITE_FIXTURE);
  await registerMockTemplate('vue-vite', VUE_VITE_FIXTURE);
}

/**
 * Tears down all mock fixtures
 * Call in afterAll() or afterEach()
 */
export function teardownAllFixtures(): void {
  unregisterMockTemplate('next-app-router');
  unregisterMockTemplate('react-vite');
  unregisterMockTemplate('vue-vite');
}

/**
 * Clears all fixtures (alias for teardownAllFixtures)
 */
export function clearAllFixtures(): void {
  clearMockTemplates();
}
