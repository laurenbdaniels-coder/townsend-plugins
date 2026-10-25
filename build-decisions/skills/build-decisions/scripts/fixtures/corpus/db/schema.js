// knex: column names are strings (review round 1, S-062)
exports.up = (knex) =>
  knex.schema.createTable('members', (table) => {
    table.increments('id');
    table.string('passport');
    table.string('label').defaultTo('a passport photo');
  });
