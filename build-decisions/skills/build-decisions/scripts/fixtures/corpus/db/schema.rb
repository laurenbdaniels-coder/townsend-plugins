# Rails writes every column name as a string (review round 1, S-062).
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000000) do
  create_table "patients", force: :cascade do |t|
    t.string "name"
    t.string "ssn"
    t.date "date_of_birth"
    t.text "notes", default: "no medical notes yet"
  end
end
