-- MySQL dump: an escaped quote must not blank the tables after it (review round 1, S-062)
INSERT INTO `people` VALUES (1,'O\'Brien'),(2,'x');
# don't edit by hand
CREATE TABLE `clinic_visits` (
  `id` int NOT NULL,
  `diagnosis` text,
  `note` varchar(20) DEFAULT 'x'
);
