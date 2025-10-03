/**
 * Our formatting configuration.
 *
 * @see https://prettier.io/docs/en/configuration.html
 * @satisfies {import("prettier").Config}
 */
const config = {
  plugins: ['@trivago/prettier-plugin-sort-imports'],
  printWidth: 140,
  tabWidth: 2,
  singleQuote: true,
  importOrder: ['^aws-cdk-lib/(.*)$', '^constructs/(.*)$', '^[./]'],
  importOrderSeparation: true,
  importOrderSortSpecifiers: true,
};

export default config;
